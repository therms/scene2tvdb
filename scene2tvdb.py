#!/usr/bin/python
# Author: Dustin Wyatt <dustin.wyatt@gmail.com>, Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
# URL: https://github.com/therms/scene2tvdb
#
#
# scene2tvdb is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# scene2tvdb is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.
import sys
import os
import shutil
import re
import datetime

##########CONFIG############
season_delta = -1 # use positive or negative integers to add or subtract from the downloaded season number
episode_delta = 7 # use positive or negative integers to add or subtract from the downloaded episode number

# a dictionary where each key is a string in the downloaded file/folder name and the value is 
# what you want to replace the key with.  CASE SENSITIVE
# If you want to remove a string set the value to ""
replace_words = {"program": "",
                "stupid string": "non stupid string",
                "another stupid string": "another non-stupid string"}

# test_mode: set to True if you don't want the script to actually move anything or call sickbeard
#  In this mode will just print what it would do if it wasn't in test mode
test_mode = False

# pass_to_sickbeard: Set to True if you want script to pass off renamed file/folder to sickbeard's post processing script
pass_to_sickbeard = False
########END CONFIG##########

if test_mode:
    import pdb

# Thanks to sickbeard for the regexes and name parser.  https://github.com/midgetspy/Sick-Beard
regexes = [
              ('standard_repeat',
               # Show.Name.S01E02.S01E03.Source.Quality.Etc-Group
               # Show Name - S01E02 - S01E03 - S01E04 - Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               s(?P<season_num>\d+)[. _-]*                 # S01 and optional separator
               e(?P<ep_num>\d+)                            # E02 and separator
               ([. _-]+s(?P=season_num)[. _-]*             # S01 and optional separator
               e(?P<extra_ep_num>\d+))+                    # E03/etc and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('fov_repeat',
               # Show.Name.1x02.1x03.Source.Quality.Etc-Group
               # Show Name - 1x02 - 1x03 - 1x04 - Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               (?P<season_num>\d+)x                        # 1x
               (?P<ep_num>\d+)                             # 02 and separator
               ([. _-]+(?P=season_num)x                    # 1x
               (?P<extra_ep_num>\d+))+                     # 03/etc and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('standard',
               # Show.Name.S01E02.Source.Quality.Etc-Group
               # Show Name - S01E02 - My Ep Name
               # Show.Name.S01.E03.My.Ep.Name
               # Show.Name.S01E02E03.Source.Quality.Etc-Group
               # Show Name - S01E02-03 - My Ep Name
               # Show.Name.S01.E02.E03
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               s(?P<season_num>\d+)[. _-]*                 # S01 and optional separator
               e(?P<ep_num>\d+)                            # E02 and separator
               (([. _-]*e|-)                               # linking e/- char
               (?P<extra_ep_num>(?!(1080|720)[pi])\d+))*   # additional E03/etc
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('fov',
               # Show_Name.1x02.Source_Quality_Etc-Group
               # Show Name - 1x02 - My Ep Name
               # Show_Name.1x02x03x04.Source_Quality_Etc-Group
               # Show Name - 1x02-03-04 - My Ep Name
               '''
               ^((?P<series_name>.+?)[\[. _-]+)?           # Show_Name and separator
               (?P<season_num>\d+)x                        # 1x
               (?P<ep_num>\d+)                             # 02 and separator
               (([. _-]*x|-)                               # linking x/- char
               (?P<extra_ep_num>
               (?!(1080|720)[pi])(?!(?<=x)264)             # ignore obviously wrong multi-eps
               \d+))*                                      # additional x03/etc
               [\]. _-]*((?P<extra_info>.+?)               # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('scene_date_format',
               # Show.Name.2010.11.23.Source.Quality.Etc-Group
               # Show Name - 2010-11-23 - Ep Name
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (?P<air_year>\d{4})[. _-]+                  # 2010 and separator
               (?P<air_month>\d{2})[. _-]+                 # 11 and separator
               (?P<air_day>\d{2})                          # 23 and separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''),

              ('stupid',
               # tpz-abc102
               '''
               (?P<release_group>.+?)-\w+?[\. ]?           # tpz-abc
               (?!264)                                     # don't count x264
               (?P<season_num>\d{1,2})                     # 1
               (?P<ep_num>\d{2})$                          # 02
               '''),

              ('verbose',
               # Show Name Season 1 Episode 2 Ep Name
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show Name and separator
               season[. _-]+                               # season and separator
               (?P<season_num>\d+)[. _-]+                  # 1
               episode[. _-]+                              # episode and separator
               (?P<ep_num>\d+)[. _-]+                      # 02 and separator
               (?P<extra_info>.+)$                         # Source_Quality_Etc-
               '''),

              ('season_only',
               # Show.Name.S01.Source.Quality.Etc-Group
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               s(eason[. _-])?                             # S01/Season 01
               (?P<season_num>\d+)[. _-]*                  # S01 and optional separator
               [. _-]*((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('no_season_multi_ep',
               # Show.Name.E02-03
               # Show.Name.E02.2010
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (e(p(isode)?)?|part|pt)[. _-]?              # e, ep, episode, or part
               (?P<ep_num>(\d+|[ivx]+))                    # first ep num
               ((([. _-]+(and|&|to)[. _-]+)|-)                # and/&/to joiner
               (?P<extra_ep_num>(?!(1080|720)[pi])(\d+|[ivx]+))[. _-])            # second ep num
               ([. _-]*(?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('no_season_general',
               # Show.Name.E23.Test
               # Show.Name.Part.3.Source.Quality.Etc-Group
               # Show.Name.Part.1.and.Part.2.Blah-Group
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (e(p(isode)?)?|part|pt)[. _-]?              # e, ep, episode, or part
               (?P<ep_num>(\d+|([ivx]+(?=[. _-]))))                    # first ep num
               ([. _-]+((and|&|to)[. _-]+)?                # and/&/to joiner
               ((e(p(isode)?)?|part|pt)[. _-]?)           # e, ep, episode, or part
               (?P<extra_ep_num>(?!(1080|720)[pi])
               (\d+|([ivx]+(?=[. _-]))))[. _-])*            # second ep num
               ([. _-]*(?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),

              ('bare',
               # Show.Name.102.Source.Quality.Etc-Group
               '''
               ^(?P<series_name>.+?)[. _-]+                # Show_Name and separator
               (?P<season_num>\d{1,2})                     # 1
               (?P<ep_num>\d{2})                           # 02 and separator
               ([. _-]+(?P<extra_info>(?!\d{3}[. _-]+)[^-]+) # Source_Quality_Etc-
               (-(?P<release_group>.+))?)?$                # Group
               '''),

              ('no_season',
               # Show Name - 01 - Ep Name
               # 01 - Ep Name
               '''
               ^((?P<series_name>.+?)[. _-]+)?             # Show_Name and separator
               (?P<ep_num>\d{2})                           # 02
               [. _-]+((?P<extra_info>.+?)                 # Source_Quality_Etc-
               ((?<![. _-])-(?P<release_group>[^-]+))?)?$  # Group
               '''
               ),
              ]

class NameParser(object):
    def __init__(self, file_name=True):

        self.file_name = file_name
        self.compiled_regexes = []
        self._compile_regexes()

    def clean_series_name(self, series_name):
        """Cleans up series name by removing any . and _
        characters, along with any trailing hyphens.

        Is basically equivalent to replacing all _ and . with a
        space, but handles decimal numbers in string, for example:

        >>> cleanRegexedSeriesName("an.example.1.0.test")
        'an example 1.0 test'
        >>> cleanRegexedSeriesName("an_example_1.0_test")
        'an example 1.0 test'

        Stolen from dbr's tvnamer
        """

        series_name = re.sub("(\D)\.(?!\s)(\D)", "\\1 \\2", series_name)
        series_name = re.sub("(\d)\.(\d{4})", "\\1 \\2", series_name) # if it ends in a year then don't keep the dot
        series_name = re.sub("(\D)\.(?!\s)", "\\1 ", series_name)
        series_name = re.sub("\.(?!\s)(\D)", " \\1", series_name)
        series_name = series_name.replace("_", " ")
        series_name = re.sub("-$", "", series_name)
        return series_name.strip()

    def _compile_regexes(self):
        for (cur_pattern_name, cur_pattern) in regexes:
            try:
                cur_regex = re.compile(cur_pattern, re.VERBOSE | re.IGNORECASE)
            except re.error, errormsg:
               print u"WARNING: Invalid episode_pattern, %s. %s" % (errormsg, cur_pattern)
            else:
                self.compiled_regexes.append((cur_pattern_name, cur_regex))

    def _parse_string(self, name):

        if not name:
            return None

        for (cur_regex_name, cur_regex) in self.compiled_regexes:
            match = cur_regex.match(name)

            if not match:
                continue

            result = ParseResult(name)
            result.which_regex = [cur_regex_name]

            named_groups = match.groupdict().keys()

            if 'series_name' in named_groups:
                result.series_name = match.group('series_name')
                if result.series_name:
                    result.series_name = self.clean_series_name(result.series_name)

            if 'season_num' in named_groups:
                tmp_season = int(match.group('season_num'))
                if cur_regex_name == 'bare' and tmp_season in (19,20):
                    continue
                result.season_number = tmp_season

            if 'ep_num' in named_groups:
                ep_num = self._convert_number(match.group('ep_num'))
                if 'extra_ep_num' in named_groups and match.group('extra_ep_num'):
                    result.episode_numbers = range(ep_num, self._convert_number(match.group('extra_ep_num'))+1)
                else:
                    result.episode_numbers = [ep_num]

            if 'air_year' in named_groups and 'air_month' in named_groups and 'air_day' in named_groups:
                year = int(match.group('air_year'))
                month = int(match.group('air_month'))
                day = int(match.group('air_day'))

                # make an attempt to detect YYYY-DD-MM formats
                if month > 12:
                    tmp_month = month
                    month = day
                    day = tmp_month

                try:
                    result.air_date = datetime.date(year, month, day)
                except ValueError, e:
                    raise InvalidNameException(e.message)

            if 'extra_info' in named_groups:
                tmp_extra_info = match.group('extra_info')

                # Show.S04.Special is almost certainly not every episode in the season
                if tmp_extra_info and cur_regex_name == 'season_only' and re.match(r'([. _-]|^)(special|extra)\w*([. _-]|$)', tmp_extra_info, re.I):
                    continue
                result.extra_info = tmp_extra_info

            if 'release_group' in named_groups:
                result.release_group = match.group('release_group')

            return result

        return None

    def _combine_results(self, first, second, attr):
        # if the first doesn't exist then return the second or nothing
        if not first:
            if not second:
                return None
            else:
                return getattr(second, attr)

        # if the second doesn't exist then return the first
        if not second:
            return getattr(first, attr)

        a = getattr(first, attr)
        b = getattr(second, attr)

        # if a is good use it
        if a != None or (type(a) == list and len(a)):
            return a
        # if not use b (if b isn't set it'll just be default)
        else:
            return b

    def _unicodify(self, obj, encoding = "utf-8"):
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj

    def _convert_number(self, number):
        if type(number) == int:
            return number

        # the lazy way
        if number.lower() == 'i': return 1
        if number.lower() == 'ii': return 2
        if number.lower() == 'iii': return 3
        if number.lower() == 'iv': return 4
        if number.lower() == 'v': return 5
        if number.lower() == 'vi': return 6
        if number.lower() == 'vii': return 7
        if number.lower() == 'viii': return 8
        if number.lower() == 'ix': return 9
        if number.lower() == 'x': return 10
        if number.lower() == 'xi': return 11
        if number.lower() == 'xii': return 12
        if number.lower() == 'xiii': return 13
        if number.lower() == 'xiv': return 14
        if number.lower() == 'xv': return 15

        return int(number)

    def parse(self, name):

        name = self._unicodify(name)

        # break it into parts if there are any (dirname, file name, extension)
        dir_name, file_name = os.path.split(name)
        ext_match = re.match('(.*)\.\w{3,4}$', file_name)
        if ext_match and self.file_name:
            base_file_name = ext_match.group(1)
        else:
            base_file_name = file_name

        # use only the direct parent dir
        dir_name = os.path.basename(dir_name)

        # set up a result to use
        final_result = ParseResult(name)

        # try parsing the file name
        file_name_result = self._parse_string(base_file_name)

        # parse the dirname for extra info if needed
        dir_name_result = self._parse_string(dir_name)

        # build the ParseResult object
        final_result.air_date = self._combine_results(file_name_result, dir_name_result, 'air_date')

        if not final_result.air_date:
            final_result.season_number = self._combine_results(file_name_result, dir_name_result, 'season_number')
            final_result.episode_numbers = self._combine_results(file_name_result, dir_name_result, 'episode_numbers')

        # if the dirname has a release group/show name I believe it over the filename
        final_result.series_name = self._combine_results(dir_name_result, file_name_result, 'series_name')
        final_result.extra_info = self._combine_results(dir_name_result, file_name_result, 'extra_info')
        final_result.release_group = self._combine_results(dir_name_result, file_name_result, 'release_group')

        final_result.which_regex = []
        if final_result == file_name_result:
            final_result.which_regex = file_name_result.which_regex
        elif final_result == dir_name_result:
            final_result.which_regex = dir_name_result.which_regex
        else:
            if file_name_result:
                final_result.which_regex += file_name_result.which_regex
            if dir_name_result:
                final_result.which_regex += dir_name_result.which_regex

        # if there's no useful info in it then raise an exception
        if final_result.season_number == None and not final_result.episode_numbers and final_result.air_date == None and not final_result.series_name:
            raise InvalidNameException("Unable to parse "+name)

        # return it
        return final_result

class ParseResult(object):
    def __init__(self,
                 original_name,
                 series_name=None,
                 season_number=None,
                 episode_numbers=None,
                 extra_info=None,
                 release_group=None,
                 air_date=None
                 ):

        _, self.extension = os.path.splitext(original_name)
        self.original_name = original_name

        self.series_name = series_name
        self.season_number = season_number
        if not episode_numbers:
            self.episode_numbers = []
        else:
            self.episode_numbers = episode_numbers

        self.extra_info = extra_info
        self.release_group = release_group

        self.air_date = air_date

        self.which_regex = None

    def adjust_numbering(self, episode_delta, season_delta):
        self.episode_numbers = [x + episode_delta for x in self.episode_numbers]
        self.season_number += season_delta

    def __eq__(self, other):
        if not other:
            return False

        if self.series_name != other.series_name:
            return False
        if self.season_number != other.season_number:
            return False
        if self.episode_numbers != other.episode_numbers:
            return False
        if self.extra_info != other.extra_info:
            return False
        if self.release_group != other.release_group:
            return False
        if self.air_date != other.air_date:
            return False

        return True

    def __str__(self):
        if self.series_name != None:
            to_return = self.series_name + u' - '
        else:
            to_return = u''
        if self.season_number != None:
            to_return += 'S'+str(self.season_number)
        if self.episode_numbers and len(self.episode_numbers):
            for e in self.episode_numbers:
                to_return += 'E'+str(e)

        if self.air_by_date:
            to_return += str(self.air_date)

        if self.extra_info:
            to_return += ' - ' + self.extra_info
        if self.release_group:
            to_return += ' (' + self.release_group + ')'

#        to_return += ' [ABD: '+str(self.air_by_date)+']'
        to_return += self.extension

        return to_return.encode('utf-8')

    def _is_air_by_date(self):
        if self.season_number == None and len(self.episode_numbers) == 0 and self.air_date:
            return True
        return False
    air_by_date = property(_is_air_by_date)

class InvalidNameException(Exception):
    "The given name is not valid"

def string_replace(orig_string, replace_words):
    """ Takes the replace_words dictionary and does all the replacements on orig_string"""
    for replace_word in replace_words:
        case_insensitive = re.compile(re.escape(replace_word), re.IGNORECASE)        
        orig_string = case_insensitive.sub(replace_words[replace_word], orig_string)        
    return orig_string.strip()

if len(sys.argv) < 2:
    print "No folder supplied "
    sys.exit()

print "moving:"
print sys.argv[1]
print "-----------------------"
print

root, orig_folder = os.path.split(sys.argv[1])

parser = NameParser(file_name=False)

# Process folder name
folder = string_replace(orig_folder, replace_words)
folder_info = parser.parse(folder)
folder_info.adjust_numbering(episode_delta, season_delta)

# Replace the season/episode id in the folder name
new_folder = os.path.join(root, folder_info.__str__())

print "to: " + new_folder
print

if not test_mode:
    shutil.move(sys.argv[1], new_folder)

if not test_mode:
    files = os.listdir(new_folder)
else:
    files = os.listdir(sys.argv[1])

parser = NameParser(file_name=True)
for f in files:
    if not test_mode:
        full_path = os.path.join(root, new_folder, f)
    else:
        full_path = os.path.join(root, orig_folder, f)
    if os.path.isfile(full_path):
        file_info = parser.parse(string_replace(f, replace_words))
        file_info.adjust_numbering(episode_delta, season_delta)
        new_f = file_info.__str__()
        if not test_mode:
            shutil.move(full_path, os.path.join(root, new_folder, new_f))
        print f + " renamed to: " + new_f

# pass fixed file/folder to sickbeard
if not test_mode:
    if pass_to_sickbeard:
        import autoProcessTV
        autoProcessTV.processEpisode(new_folder)
