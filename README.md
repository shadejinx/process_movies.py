# process_movies.py
Process movies based on quality

## Process and disposition movie downloads automatically
This script is really meant for my library and how I've configured my Plex server. It if works for you, I'll be very surprised. 

That out of the way, here's what it does:
  * Reads the filename of the movie and parses out the <title> and <year> (using the Parse Torrent Name library)
  * Connects to TheMovieDB to fix the title and get movie genre. (using FuzzyWuzzy fuzzy string matching)
  * Opens the movie with FFProbe to get video and audio quality information (using FFProbe, duh)
  * Connects to the Plex database to see if the movie already exists in the library, if so:
  - If so, it compares the video and audio quality information to determine which is better
  ** If not, it performs a quality check on the movies to determine if its good enough to add to the library
  *** Movies that are considered borderline are added to a staging directory for manual processing
  *** Movies that do not meet quality standards are deleted.

### Usage: process_movies.py [-d|--dry-run] [-v|--verbose] [-r|--replace] -f <movie>
  -d|--dry-run    Disposition file but don't perform any file operations
  -v|--verbose    Increase logging
  -r|--replace    Replace file in Plex library if it's deemed better
 
 
