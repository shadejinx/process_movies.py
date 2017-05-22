def getFFProbeInfo( inFile, inStream ):
### getFFProbeInfo
#       Input: filename (string), [v, a, s] (string)
#       Output: res (JSON object)
#               Errors to None

        res = None

        if os.path.isfile( inFile ) and inStream in ['a', 'v', 's']:
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
#       Input: inJSON (JSON object)
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
#       Input: inCodec (string)
#       Output: codec (string)
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
#       Input: inJSON (JSON object)
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

