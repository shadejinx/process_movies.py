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

                        if ( row_chan >= channels and row_bit >= bitrate ) or not codec:
                                channels = row_chan
                                bitrate = row_bit
                                codec = row_codec

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
