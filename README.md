# process_movies.py
Process movies based on quality

## Process and disposition movie downloads automatically
This script is really meant for my library and how I've configured my Plex server. It if works for you, I'll be very surprised. I'm also a really new python coder, so please save the comments about my shitty code... unless you have a sweet tip on how to make it more efficient. 

That out of the way, here's what it does:
  * Reads the filename of the movie and parses out the [title] and [year] (using the Parse Torrent Name library)
  * Connects to TheMovieDB to fix the title and get movie genre. (using FuzzyWuzzy fuzzy string matching)
  * Opens the movie with FFProbe to get video and audio quality information (using FFProbe, duh)
  * Connects to the Plex database to see if the movie already exists in the library:
  	* If so, it compares the video and audio quality information to determine which is better
    * If not, it performs a quality check on the movie to determine if its good enough to add to the library
    * Movies that are considered borderline are added to a staging directory for manual processing
    * Movies that do not meet quality standards are deleted.

Quality is completely subjective and a script can't suss out any of that, but it can determine the quality of the encode at the nuts and bolts level. For the most part, downloaded movies fit within only a few quality buckets, and by using BPP, the rule of 0.75 and genre, this scrip can go a long way in weeding out shitty encodes from your library. Is it perfect, hell no, but its a good first step in managing your downloads.

Here's the basis of my file dispositions:
1. If the movie is 4:3 __and__ is newer than 1977, delete it. (1977 is arbitrary, but it is also the year of Star Wars)
2. If the movie doesn't have a BPP greater than 0.04, delete it.
3. If the movie doesn't include enough metadata information to disposition, delete it (e.g. codec, bitrate, framerate, etc.)
4. If the movie is older than 1977, be more lienient
5. If the movie belongs to certain genres, be more stringent (e.g. Action, Adventure, Sci-Fi, etc.)
6. If the movie already exists in the Plex library, the new file must be at least 20% better to consider replacement
7. Preference is given to newer codecs, english audio or subtitles and 6 channel (or better) audio 

## Dependencies
* This script will require the parse-torrent-name and fuzzywuzzy python libraries. They both can be installed with pip. 
* FFProbe will need to be installed. I run this on an Ubuntu installation so it's located in /usr/bin/ffprobe
* You will also need a TheMovieDB API key. You get that by signing up for an account and visiting your settings page.

## Usage 
### process_movies.py [-d|--dry-run] [-v|--verbose] [-r|--replace] [--mvdb-api-key] -f movie_file
* -d|--dry-run&nbsp;&nbsp;&nbsp;&nbsp;Disposition file but don't perform any file operations
* -v|--verbose&nbsp;&nbsp;&nbsp;&nbsp;Increase logging
* -r|--replace&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Replace file in Plex library if it's deemed better
* --mvdb-api-key&nbsp;&nbsp;&nbsp;&nbsp;MVDB API Key
 
## Known Issues
* The parse-torrent-name library isn't perfect and has problems with files with 'Web-DL' in the title.
* Movie metadata is very inconsistent. I've tried to normalize as much as I can with the data sources I have available to me, but I understand my dataset is small. If it doesn't work for your data set, again... I'm not surprised.
* This script is VERY english-centric.

