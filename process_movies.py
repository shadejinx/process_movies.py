#!/usr/bin/python

from __future__ import division
import PTN
import argparse
import requests
import json
import os
import sys
import subprocess
import logging
import shutil
import sqlite3
from fuzzywuzzy import fuzz

library_dir = '/mnt/movies'
staging_dir = '/mnt/.local/media/video/staging'

plexdb = '/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db'
plex_library_name = 'Movies'

log_file = '/var/log/aria2/process_file.log'

tvdb_apikey = TVDB_API_KEY

codeclist = [ 'mpeg2', 'h265', 'h264', 'mpeg4' ]

#######

def getFFProbeInfo( inFile, inStream ):
### getFFProbeInfo
#       Input: filename, [v, a]
#       Output: JSON object
#               Errors to None

        res = None

        if os.path.isfile( inFile ) and inStream in ['a','v']:
                cmd = [ '/usr/bin/ffprobe' ]
                arg = '-v quiet -print_format json -select_streams ' + inStream + ': -show_streams'

                cmd = cmd + arg.split()
                cmd.append(inFile)

                try:
                        output = subprocess.check_output( cmd )
                except Exception, e:
                        output = None

                if output:
                        try:
                                res = json.loads(output)
                        except ValueError:
                                res = None
        return res


def getVideoInfo( inJSON ):
### getVideoInfo
#       Input: JSON object from FFProbe
#       Output: codec (string), birate (int), aspect (float), pixels (int), framerate (float)
#               Errors to None

        try:
                isJSON = json.dumps(inJSON)
        except ValueError:
                isJSON = None

        if isJSON and inJSON['streams']:
                stream = inJSON['streams'][0]

                codec = stream.get('codec_name').lower()
                aspect = stream.get('display_aspect_ratio')
                width = stream.get('width')
                height = stream.get('height')
                bitrate = stream.get('bit_rate')
                framerate = stream.get('avg_frame_rate')

                codec = mungeCodec(codec) if codec else None

                if not bitrate and stream.get('tags'):
                        bitrate = stream['tags'].get('BPS')

                if ':' in aspect:
                        ratio = aspect.split(':')
                        aspect = round((int(ratio[0]) / int(ratio[1])),3)

                if not aspect:
                        aspect = round((int(width) / int(height)), 3)

                if '/0' in framerate:
                        framerate = stream.get('r_frame_rate')

                if '/' in framerate and '/0' not in framerate:
                        rate = framerate.split('/')
                        framerate = round((int(rate[0]) / int(rate[1])),3)
                else:
                        framerate = 0

                pixels = int(width) * int(height) if width and height else 0

                codec = str(codec) if codec else None
                bitrate = int(bitrate) if bitrate else None
                aspect = float(aspect) if aspect else None
                pixels = int(pixels) if pixels else None
                framerate = float(framerate) if framerate else None

                return codec, bitrate, aspect, pixels, framerate


def mungeCodec( inCodec ):
### mungeCodec
#       Input: String representing a codec
#       Output: String
#               Errors to None

        codec = str(inCodec) if isinstance( inCodec, basestring ) else None

        if codec:
                if 'mpeg2' in codec or 'mpeg-2' in codec:
                        codec = 'mpeg2'
                elif 'hev' in codec or 'h265' in codec:
                        codec = 'h265'
                elif 'avc' in codec or 'h264' in codec:
                        codec = 'h264'
                elif codec in [ 'dx50', 'xvid', 'div3', 'divx' ] or 'mpeg-4' in codec or 'mpeg4' in codec:
                        codec = 'mpeg4'
                else:
                        codec = 'unknown'

        codec = str(codec) if codec else None

        return codec


def getAudioInfo( inJSON ):
### getAudioInfo
#       Input: JSON object
#       Output: language (string), channels (int), bitrate (string)
#               Errors to None
        try:
                isJSON = json.dumps(inJSON)
        except ValueError:
                isJSON = None

        codec = None
        bitrate = None
        channels = None
        language = None

        if isJSON and inJSON['streams']:
                stream = inJSON['streams']
                en_bit = 0
                en_chan = 0
                en_codec = None
                english = False
                foreign = False

                for idx in range(len(stream)):
                        idx_codec = stream[idx].get('codec_name')
                        idx_bit = stream[idx].get('bit_rate')
                        idx_chan = stream[idx].get('channels')
                        idx_lang = None

                        if stream[idx].get('tags'):
                                idx_lang = stream[idx]['tags'].get('language')
                                if idx_lang and idx_lang.lower() in [ 'en', 'eng', 'english' ]:
                                        english = True
                                        if int(idx_chan) >= int(en_chan):
                                                en_chan = idx_chan
                                                en_bit = idx_bit
                                                en_codec = idx_codec
                                elif idx_lang and idx_lang != 'und':
                                        foreign = True

                        if not idx_bit and stream[idx].get('tags'):
                                idx_bit = stream[idx]['tags'].get('BPS')

                        if idx_chan and idx_bit and int(idx_chan) >= channels and int(idx_bit) >= bitrate:
                                channels = idx_chan
                                bitrate = idx_bit
                                codec = idx_codec

                        if not codec:
                                codec = idx_codec
                                bitrate = idx_bit
                                channels = idx_chan

                if english:
                        language = 'english'
                        channels = en_chan
                        bitrate = en_bit
                        codec = en_codec
                elif foreign:
                        language = 'foreign'
                else:
                        language = 'unknown'

        codec = str(codec) if codec else None
        bitrate = int(bitrate) if bitrate else None
        channels = int(channels) if channels else None
        language = str(language) if language else None

        return codec, language, channels, bitrate


def hasEngSubtitles( inJSON ):
### getSubtitleInfo
#       Input : inJSON (json)
#       Output: has_eng_subtitle (BOOL)
#               Errors to False

        try:
                isJSON = json.dumps(inJSON)
        except ValueError:
                isJSON = None

        has_eng_subtitle = False

        if isJSON and inJSON['streams']:
                stream = inJSON['streams']

                for idx in range(len(stream)):
                        idx_lang = stream[idx].get('language')

                        if idx_lang.lower() in [ 'en', 'eng', 'english' ]:
                                has_eng_subtitle = True
                                break

        return has_eng_subtitle


def queryPlexDB( inQuery ):
### queryPlexDB
#       Input : inQuery (string), plexdb (Global string)
#       Output: rows (list of lists)
#               Errors to None

        query = str(inQuery) if inQuery else ''
        rows = None

        if query:
                db_conn = sqlite3.connect(plexdb)
                db = db_conn.cursor()
                db.execute( query )
                rows = db.fetchall()
                db_conn.close()

        return rows


def getPlexSectionID( inSectionName ):
### getPlexSectionID
#       Input : inSectionName (string)
#       Output: section_id (int)
#               Errors to None

        section_name = str(inSectionName) if inSectionName else ''

        section_id = None

        query = '       SELECT  id, name \
                        FROM    library_sections \
                        WHERE   name = "' + str(section_name) + '";'

        row = queryPlexDB( query )

        if row:
                section_id = row[0][0]

        section_id = int(section_id) if section_id else None

        return section_id


def getPlexMediaID( inTitle, inYear, inSection ):
### getPlexMediaID
#       Input : inTitle (string), inYear (int), inSection (int)
#       Output: media_id (int)
#               Errors to 0

        title = str(inTitle) if inTitle else ''
        year = int(inYear) if inYear else 0
        section = int(inSection) if inSection else 0

        old_score = None
        media_id = None

        query = '       SELECT  metadata_items.title, metadata_items.year, \
                                media_items.id \
                        FROM    metadata_items JOIN media_items \
                        WHERE   metadata_items.id = media_items.metadata_item_id \
                                AND metadata_items.library_section_id = ' + str(section) + ';'

        rows = queryPlexDB( query )

        for row in rows:
                row_title = row[0]
                row_year = row[1]
                row_id = row[2]

                if year == row_year:
                        score = int(fuzz.token_sort_ratio( title, row_title ))
                        if score > 85 and score > old_score:
                                old_score = score
                                media_id = row_id

        media_id = int(media_id) if media_id else 0

        return media_id


def getPlexFileInfo ( inMediaID ):
### getPlexFileInfo
#       Input: inMediaID (int)
#       Output: filename (string), directory (string)
#               Errors to None

        media_id = int(inMediaID) if inMediaID else 0

        directory = None
        filename = None

        query = '       SELECT  directories.path, \
                                media_parts.file \
                        FROM    directories JOIN media_parts \
                        WHERE   directories.id = media_parts.directory_id \
                                AND media_parts.media_item_id = ' + str(media_id) + ';'

        row = queryPlexDB( query )

        if row:
                directory = row[0][0]
                filename = row[0][1]

        directory = str(directory) if directory else None
        filename = os.path.abspath(filename) if filename else None

        return directory, filename


def getPlexVideoInfo( inMediaID ):
### getPlexVideoInfo
#       Input: inMediaID (int)
#       Output: codec (string), bitrate (int), pixels (int), framerate (float)
#               Errors to None

        media_id = int(inMediaID) if inMediaID else 0

        codec = None
        bitrate = None
        pixels = None
        fps = None

        query = '       SELECT  media_items.width, media_items.height, media_items.frames_per_second, \
                                media_streams.codec, media_streams.bitrate \
                        FROM    media_items JOIN media_streams \
                        WHERE   media_items.id = media_streams.media_item_id \
                                AND media_items.video_codec = media_streams.codec \
                                AND media_items.id = ' + str(media_id) + ';'

        row = queryPlexDB( query )

        if row:
                width = row[0][0]
                height = row[0][1]
                fps = row[0][2]
                codec = row[0][3]
                bitrate = row[0][4]

        if width and height:
                pixels = int(width) * int(height)

        codec = str(mungeCodec( codec )) if codec else None
        bitrate = int(bitrate) if bitrate else None
        pixels = int(pixels) if pixels else None
        fps = float(fps) if fps else None

        return codec, bitrate, pixels, fps


def getPlexAudioInfo( inMediaID ):
### getPlexMediaID
#       Input: inMediaID (int)
#       Output: codec (string), language (string), channels (int), bitrate (int)
#               Errors to None

        media_id = int(inMediaID) if inMediaID else 0

        codec = None
        language = None
        channels = 0
        bitrate = 0
        en_chan = 0
        en_bit = 0
        en_codec = None
        english = False
        foreign = False

        query = '       SELECT  media_streams.codec, media_streams.language, media_streams.channels, media_streams.bitrate \
                        FROM    media_streams JOIN media_items \
                        WHERE   media_streams.media_item_id = ' + str(media_id) + ' \
                                AND media_streams.media_item_id = media_items.id;'

        rows = queryPlexDB( query )

        for row in rows:
                row_codec = row[0]
                row_lang = row[1]
                row_chan = row[2]
                row_bit = row[3]

                if row_codec.lower() in [ 'aac', 'ac3', 'eac3', 'dca', 'mp3', 'wmav1', 'wmav2' ]:
                        if row_lang and row_lang == 'eng':
                                english = True
                                if row_chan >= en_chan:
                                        en_chan = row_chan
                                        en_bit = row_bit
                                        en_codec = row_codec
                        elif row_lang:
                                foreign = True

                        if row_chan >= channels and row_bit >= bitrate:
                                channels = row_chan
                                bitrate = row_bit
                                codec = row_codec

                        if not codec:
                                codec = row_codec
                                bitrate = row_bit
                                channels = row_chan

        if english:
                language = 'english'
                channels = en_chan
                bitrate = en_bit
                codec = en_codec
        elif foreign:
                language = 'foreign'
        else:
                language = 'unknown'

        codec = str(codec) if codec else None
        language = str(language) if language else None
        channels = int(channels) if channels else None
        bitrate = int(bitrate) if bitrate else None

        return codec, language, channels, bitrate


def getTVDBResult( inTitle, inYear ):
### getTVDBResult
#       Input: Title (string), Year (int)
#       Output: JSON blob
#               Errors to None

        title = str(inTitle) if inTitle else ''
        year = int(inYear) if inYear else 0

        url = "https://api.themoviedb.org/3/search/movie"
        isJSON = False

        payload = {'api_key' : tvdb_apikey, 'query' : inTitle, 'year' : inYear }
        response = requests.request("GET", url, data=payload)

        if response.status_code == requests.codes.ok:
                res_json = response.json()

        try:
                json.dumps(res_json)
                isJSON = True
        except ValueError:
                isJSON = False

        if isJSON:
                return( res_json['results'] )
        else:
                return( None )


def calcVideoScore( inCodec, inBitrate, inPixels, inFramerate ):
### calcVideoScore
#       Input: codec (string), bitrate (int), pixels (int), framerite (float)
#       Outout: score (int)
#               Errors to 0

        codec = str(inCodec) if inCodec else ''
        bitrate = int(inBitrate) if inBitrate else 0
        pixels = int(inPixels) if inPixels else 0
        framerate = float(inFramerate) if inFramerate else 0

        score = 0

        if pixels and framerate:
                bpp = bitrate / ( pixels * framerate )
        else:
                bpp = 0

        for i in [ .05, .08, 0.1, .2, 1 ]:
                if bpp > i:
                        continue
                else:
                        score = [ .05, .08, 0.1, .2, 1 ].index(i)
                        break

        score += 1 if codec == 'h265' else 0

        score = int(score) if score else 0

        return score


def calcAudioScore( inCodec, inBitrate, inChannels, inLanguage, inSubtitles ):
### calcAudioScore
#       Input : inCodec (string), inBitrate (int), inChannels (int), inLanguage (string), inSubtitles (BOOL)
#       Output: score (int)
#               Errors to 0

        codec = str(inCodec) if inCodec else ''
        bitrate = int(inBitrate) if inBitrate else 0
        channels = int(inChannels) if inChannels else 0
        language = str(inLanguage) if inLanguage else 'unknwon'
        subtitles = True if inSubtitles else False

        score = 0

        score += 2 if channels >= 6 else 0

        if ( not language == 'english' and subtitles ) or language == 'english':
                score += 2

        for i in [ 98000, 127000, 150000, 256000, 100000000 ]:
                if bitrate > i:
                        continue
                else:
                        score += [ 98000, 127000, 150000, 256000, 100000000 ].index(i)
                        break

        score += 1 if codec in [ 'ac3', 'eac3', 'dca' ] else 0

        score = int(score) if score else 0

        return score


def calcTotalScore( inVideoScore, inAudioScore, inYear, inHighDef ):
### caclTotalScore
#       Input : inVideoScore (int), inAudioScore (int), inYear (int), inHighDef (BOOL)
#       Output: total_score (float)
#               Errors to None

        vid_score = int(inVideoScore) if inVideoScore else 0
        aud_score = int(inAudioScore) if inAudioScore else 0
        year = int(inYear) if inYear else 0
        high_def = True if inHighDef else False

        score = 0

        if year < 1977:
                # Be more lenient on classic movies
                score = vid_score * 1.2 + aud_score * 1.5
        elif high_def:
                # Be more stringent on genres that generally require a higher quality encode
                score = vid_score * 0.9 + aud_score * 0.75
        else:
                score = vid_score + aud_score * 0.9

        score = float(score) if score else 0

        return score


### CONFIGURE LOGGING
log = logging.getLogger('process_files.py')
log_hdlr = logging.FileHandler(log_file)
log_fmt = logging.Formatter('%(asctime)s [%(process)d] %(levelname)s: %(message)s')
log_hdlr.setFormatter(log_fmt)
log.addHandler(log_hdlr)
log.setLevel(logging.INFO)


### CONFIGURE ARGUMENT PARSING
aparse = argparse.ArgumentParser(description='Process movie files into Plex')
aparse.add_argument('-f', '--file', dest='file', required=True, help='a file to process')
aparse.add_argument('-d', '--dry-run', dest='dryrun', action='store_true', help='process files but do not move them')
aparse.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='get more detail')
aparse.add_argument('-r', '--replace', dest='replace', action='store_true', help='replace files in your library if better exists')
args = aparse.parse_args()

full_path = os.path.abspath(args.file)
verbose = args.verbose
replace = args.replace
dryrun = args.dryrun

if verbose:
        log.setLevel(logging.DEBUG)


### START PROCESSING FILE
if not os.path.exists(full_path):
        log.error('#### FINISH: File does not exist: ' + full_path)
        sys.exit(1)

log.info('#### START: Processing: ' + full_path )
if dryrun:
        log.info('Dry Run enabled, no file operations will be performed')
if replace:
        log.info('Replace enabled')

src_file = os.path.basename(full_path)


### GET MEDIAINFO INFORMATION FROM FILE
video = getFFProbeInfo( full_path, 'v' )
if video:
        codec, bitrate, ratio, pixels, framerate = getVideoInfo( video )
else:
        log.error('#### FINISH: Error reading: ' + full_path)
        sys.exit(1)

codec = '' if not codec else codec
bitrate = 0 if not bitrate else bitrate
ratio = 0 if not ratio else ratio
pixels = 0 if not pixels else pixels
framerate = 0 if not framerate else framerate

audio = getFFProbeInfo( full_path, 'a' )
if audio:
        aud_codec, language, channels, aud_bitrate = getAudioInfo( audio )
else:
        log.error('#### FINISH: Error reading: ' + full_path)
        sys.exit(1)

aud_codec = '' if not aud_codec else aud_codec
language = '' if not language else language
channels = 0 if not channels else channels
aud_bitrate = 0 if not aud_bitrate else aud_bitrate

subtitles = getFFProbeInfo( full_path, 's' )

if subtitles:
        eng_subtitles = hasEnglishSubtitles( subtitles )
else:
        eng_subtitles = False

bpp = bitrate / ( pixels * framerate )


### PARSE FILE AND PATH INFORMATION FOR MOVIE TITLE AND DATE
file_info = PTN.parse(src_file)

if 'episode' in file_info:
        log.error('#### FINISH: TV show detected, skipping.')
        sys.exit(1)

if not 'title' in file_info or not 'year' in file_info:
        log.warn('Filename parsing failure for ' + src_file + ', fuzzy matching on path.')
        parent_dir = os.path.basename(os.path.dirname(full_path))

        file_info = PTN.parse(parent_dir)

        if not 'title' in file_info or not 'year' in file_info:
                log.error('#### FINISH: Failure parsing path ' + parent_dir + ', manual processing needed.')
                sys.exit(1)

title = file_info['title'].replace('.',' ').strip(",'!%/ ").title()
year = str(file_info['year'])


### SEARCH TVDB FOR INFORMATION
log.debug('Checking TVDB for: \'' + title + '\' in ' + year )
res = getTVDBResult( title, year )

if not res:
        log.warn('No results from TVDB for: \'' + title + '\' in ' + year)
        if '-' in title or ':' in title:
                split_title = title.replace('-', ':').strip().split(':')
                log.debug('Attempting munge title: \'' + split_title[0] + '\' in ' + year)
                res = getTVDBResult( split_title[0], year )

        if not res:
                log.error('#### FINISH: No results from TVDB, check ' + src_file + ' for naming errors.')
                sys.exit(1)

prev_score = None

for idx in range(len(res)):
        if year in res[idx]['release_date']:
                title_len = len(title)
                res_len = len(res[idx]['title'])
                threshold = 55 + (( 1 - ( abs(title_len - res_len) / max(title_len, res_len))) * 30 )
                score = fuzz.token_sort_ratio(title.lower(), res[idx]['title'].lower())
                if score >= threshold and score > prev_score:
                        prev_score = score
                        tvdb_title = res[idx]['title'].lower()
                        tvdb_date = res[idx]['release_date']
                        tvdb_language = res[idx]['original_language']
                        tvdb_genres = res[idx]['genre_ids']

if not prev_score:
        log.warn('A definitive match cannot be found in TVDB, munging title and searching again')
        if str(year) in res[0]['release_date'] or str(int(year) - 1) in res[0]['release_date'] or str(int(year) + 1) in res[0]['release_date']:
                if ':' in res[0]['title'] or '-' in res[0]['title']:
                        split_tvdb = res[0]['title'].replace('-', ':').split(':')
                        munge_title = split_tvdb[0].lower()
                        threshold = 90
                else:
                        title_len = len(title)
                        res_len = len(res[0]['title'])
                        munge_title = res[0]['title'].lower()
                        threshold = 55 + (( 1 - ( abs(title_len - res_len) / max(title_len, res_len))) * 25 )

                score = fuzz.token_sort_ratio( title.lower(), munge_title )
                if score >= threshold:
                        prev_score = score
                        tvdb_title = res[0]['title'].lower()
                        tvdb_date = res[0]['release_date']
                        tvdb_language = res[0]['original_language']
                        tvdb_genres = res[0]['genre_ids']

if prev_score:
        log.debug('TVDB match at ' + str(prev_score) + '%: ' + title + ', ' + year + ' => ' +  tvdb_title.title() + ', ' + tvdb_date )
        title = tvdb_title.strip(",'!%/").replace(":", " -").title()
else:
        log.error('#### FINISH: TVDB has results but a definitive match was not found, edit filename and try again' )
        sys.exit(1)


#TVDB Genres
# 12:Adventure, 14:Fantasy, 16:Animation, 27:Horror, 28:Action, 878:Science-Fiction

### If file is in one of the above genres, it wants for a higher quality file
high_def = False

for genre in [ 12, 14, 16, 27, 28, 878 ]:
        if genre in tvdb_genres:
                high_def = True
                break


### SEARCH PLEX DATABASE FOR FILE
dest_dir = title + ' (' + year + ')'
duplicate = False

plex_section_id = getPlexSectionID( plex_library_name )

if plex_section_id:
        plex_media_id = getPlexMediaID( title, year, plex_section_id )

        if plex_media_id:
                duplicate = True
                old_dir, old_file = getPlexFileInfo( plex_media_id )

                old_dir = '' if not old_dir else old_dir
                old_file = '' if not old_file else old_file

                old_codec, old_bitrate, old_pixels, old_fps = getPlexVideoInfo( plex_media_id )

                old_codec = '' if not old_codec else old_codec
                old_bitrate = 0 if not old_bitrate else old_bitrate
                old_pixels = 0 if not old_pixels else old_pixels
                old_fps = 0 if not old_fps else old_fps

                old_aud_codec, old_lang, old_channels, old_aud_bitrate = getPlexAudioInfo( plex_media_id )

                old_aud_codec = '' if not old_aud_codec else old_aud_codec
                old_lang = 'unknown' if not old_lang else old_lang
                old_channels = 0 if not old_channels else old_channels
                old_aud_bitrate = 0 if not old_bitrate else old_bitrate
else:
        log.error('#### FINISH: Plex section does not exist: ' + plex_section_id)
        sys.exit(1)


### DISPOSITION THE FILE
remove = False
staging = False
error = 0

if ( int(year) >= 1977 and ratio < 1.34 ) or bitrate < ( pixels * framerate ) * 0.04:
        log.error('Movie does not meet bare minimum requirements.')
        remove = True
        error = 1

elif codec == 'unknown':
        log.error('Movie video codec unknown.')
        staging = True

elif duplicate and ( not old_pixels or not old_bitrate ):
        log.error('File found in the Plex library, but not analyzed yet. Analyze "' + title + '" in Plex and rerun this script.')
        error = 1

elif not duplicate:
        log.debug('Found in the Plex library: FALSE')

        ### Check video quality
        log.debug('Video Stats: ' + codec + ', ' + str(int( bitrate / 1000 )) + 'kbps, ' + str(int( pixels / 1000 )) + 'k pixels.' )
        log.debug('Bits-Per-Pixel (BPP): ' + str(round(bpp, 3)))

        log.debug('High-def genre: ' + str(high_def).upper() )

        vid_score = calcVideoScore( codec, bitrate, pixels, framerate )

        ### SCORE AUDIO
        log.debug('Audio Stats: ' + language + ', ' + str(channels) + ' channels, ' + str(int( aud_bitrate / 1000 )) + 'kbps' )


        aud_score = calcAudioScore( aud_codec, aud_bitrate, channels, language, eng_subtitles )

        if language == 'english':
                log.debug('English audio track: TRUE')
        else:
                log.debug('English audio track: FALSE')

        log.debug('English subtitles: ' + str(eng_subtitles).upper())

        total_score = calcTotalScore( vid_score, aud_score, year, high_def )

        log.debug('Total quality score: ' + str(total_score))

        if total_score <= 3:
                remove = True
        elif total_score <= 8:
                staging = True

else:
        log.warn('Found in Plex library: TRUE')
        log.debug('Duplicate found in ' + old_file)

        estimated_bitrate = ( ( pixels / old_pixels ) ** 0.75 ) * old_bitrate
        old_bpp = old_bitrate / ( old_pixels * old_fps )

        #### VIDEO COMPARISON
        log.debug('Video Stats, OLD: ' + old_codec + ', ' + str(int( old_bitrate / 1000 )) + 'kbps, ' + str(int( old_pixels / 1000 )) + 'k pixels, BPP: ' + str(round(old_bpp, 3)) )
        log.debug('Video Stats, NEW: ' + codec + ', ' + str(int( bitrate / 1000 )) + 'kbps, ' + str(int( pixels / 1000 )) + 'k pixels, BPP: ' + str(round(bpp, 3)) )
        log.debug('Target bitrate for the rule of 0.75 is: ' + str(int( estimated_bitrate / 1000 )) + 'kbps.' )

        old_vidscore = calcVideoScore( old_codec, old_bitrate, old_pixels, old_fps )
        vidscore = calcVideoScore( codec, bitrate, pixels, framerate )

        log.debug('High-def genre: ' + str(high_def).upper() )

        # If the codec is the same, then the bitrate must be 20% than the rule of 0.75
        if codec == old_codec and int(bitrate) >= ( estimated_bitrate * 1.2 ):
                log.debug('Movie codec is equal and bitrate is at least 20% better than the previous.')

        # If the codec is better, the bitrate must be at least 75% of the rule of 0.75
        elif codeclist.index(codec) < codeclist.index(old_codec) and int(bitrate) >= ( estimated_bitrate * 0.75 ):
                log.debug('Movie codec is better and bitrate is at least 75% of the previous.')

        #If the codec is worse, the bitrate must be at least 170% of the rule of 0.75
        elif codeclist.index(codec) - codeclist.index(old_codec) == 1 and int(bitrate) >= ( estimated_bitrate * 1.7 ):
                log.debug('Movie codec is older, but the bitrate is more than 170% of the previous.')
                staging = True

        else:
                log.warn('Movie codec is older than previous and/or it does not meet bitrate target.')
                remove = True

        #### AUDIO COMPARISON
        log.debug('Audio Stats, OLD: ' + old_lang + ', ' + old_aud_codec + ', ' + str(old_channels) + ' channels, ' + str(int( old_aud_bitrate / 1000 )) + 'kbps.')
        log.debug('Audio Stats, NEW: ' + language + ', ' + aud_codec + ', ' + str(channels) + ' channels, ' + str(int( aud_bitrate / 1000 )) + 'kbps.')
        if ( channels >= old_channels or channels >= 6 ) and int(aud_bitrate) > 150000:
                log.debug('Movie audio track quality meets or exceeds the previous.')
        elif channels == 0 or int(aud_bitrate) == 0:
                log.debug('Movie audio track quality unknown.')
                staging = True
        else:
                log.warn('Movie audio track quality does not meet the standard of the previous.')
                remove = True

        old_audscore = calcAudioScore( old_aud_codec, old_aud_bitrate, old_channels, old_lang, False )
        audscore = calcAudioScore( aud_codec, aud_bitrate, channels, language, eng_subtitles )

        old_totalscore = calcTotalScore( old_vidscore, old_audscore, year, high_def )
        totalscore = calcTotalScore( vidscore, audscore, year, high_def )

        log.debug('Total Quality Score, OLD: ' + str(round(old_totalscore, 3)))
        log.debug('Total Quality Score, NEW: ' + str(round(totalscore, 3)))

        if totalscore > old_totalscore and totalscore > 3 and remove == True:
                remove = False
                staging = True


if remove:
        log.error('#### FINISH: ' + src_file + ' does not meet standards, deleting it.')
        if not dryrun:
                os.remove(full_path)
        error = 1
elif staging:
        log.info('#### FINISH: Unable to disposition ' + src_file + ', moving to staging.')
        if not dryrun:
                if not os.path.isdir( staging_dir + '/' + dest_dir ):
                        os.mkdir( staging_dir + '/' + dest_dir )
                shutil.move( full_path, staging_dir + '/' + dest_dir + '/' + src_file )
elif duplicate and replace:
        log.warn('#### FINISH: Replacing old file in Plex library: ' + old_filename + '.' )
        if not dryrun:
                shutil.move( full_path, old_filename )
else:
        log.info('#### FINISH: Copying ' + src_file + ' to Plex library.')
        out_file, out_ext = os.path.splitext(src_file)
        out_file = title + ' (' + year + ')' + out_ext
        if not dryrun:
                if not os.path.isdir( library_dir + '/' + dest_dir ):
                        os.mkdir( library_dir + '/' + dest_dir )
                shutil.move( full_path, library_dir + '/' + dest_dir + '/' + out_file )

sys.exit(error)
