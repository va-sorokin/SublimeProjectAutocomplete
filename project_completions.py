# Extends Sublime Text autocompletion to find matches in all open
# files. By default, Sublime only considers words from the current file.

import sublime_plugin
import sublime
import re
import time
import os
import os.path
import json

# limits to prevent bogging down the system
MIN_WORD_SIZE = 3
MAX_WORD_SIZE = 50

MAX_FILES = 50
MAX_WORDS_PER_FILE = 200
MAX_FIX_TIME_SECS_PER_VIEW = 0.01


class ProjectAutocomplete(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        words = []

        # Limit number of files but always include the active opened file. This
        # view goes first to prioritize matches close to cursor position.
        words = get_words_from_view(prefix, view, locations)
        words.extend(get_words_from_files(prefix, view.window))

        words = without_duplicates(words)
        matches = []
        for word, filename in words:
            trigger = word
            contents = word.replace('$', '\\$')
            if len(filename) > 0:
                trigger += '\t(%s)' % os.path.basename(filename)
            matches.append((trigger, contents))
        return matches


def get_words_from_view(prefix, view, locations):
    words = []
    if len(locations) > 0:
        words = view.extract_completions(prefix, locations[0])
    else:
        words = view.extract_completions(prefix)
    words = filter_words(words)
    words = fix_truncation(view, words)
    return [(word, "") for word in words]


def get_words_from_files(prefix, window):
    words = []
    project_data = json.loads(window.project_data())
    folders = project_data["folders"]
    for folder in folders:
        path = folder["path"]
        files = os.listdir(path)
        for filename in files:
            file_words = get_words_from_file(filename, prefix)
            file_words = filter_words(file_words)
            words += [(word, filename) for word in file_words]

    return words


def get_words_from_file(filename, prefix):
        # TODO: get words from files here
        pass


def filter_words(words):
    words = words[0:MAX_WORDS_PER_FILE]
    return [w for w in words if MIN_WORD_SIZE <= len(w) <= MAX_WORD_SIZE]


# keeps first instance of every word and retains the original order
# (n^2 but should not be a problem as len(words) <= MAX_VIEWS*MAX_WORDS_PER_VIEW)
def without_duplicates(words):
    result = []
    used_words = []
    for w, v in words:
        if w not in used_words:
            used_words.append(w)
            result.append((w, v))
    return result


# Ugly workaround for truncation bug in Sublime when using view.extract_completions()
# in some types of files.
def fix_truncation(view, words):
    fixed_words = []
    start_time = time.time()

    for i, w in enumerate(words):
        # The word is truncated if and only if it cannot be found with a word boundary before and after

        # this fails to match strings with trailing non-alpha chars, like
        # 'foo?' or 'bar!', which are common for instance in Ruby.
        match = view.find(r'\b' + re.escape(w) + r'\b', 0)
        truncated = is_empty_match(match)
        if truncated:
            # Truncation is always by a single character, so we extend the word by one word character before a word boundary
            extended_words = []
            view.find_all(r'\b' + re.escape(w) + r'\w\b', 0, "$0", extended_words)
            if len(extended_words) > 0:
                fixed_words += extended_words
            else:
                # to compensate for the missing match problem mentioned above, just
                # use the old word if we didn't find any extended matches
                fixed_words.append(w)
        else:
            # Pass through non-truncated words
            fixed_words.append(w)

        # if too much time is spent in here, bail out,
        # and don't bother fixing the remaining words
        if time.time() - start_time > MAX_FIX_TIME_SECS_PER_VIEW:
            return fixed_words + words[i+1:]

    return fixed_words


if sublime.version() >= '3000':
    def is_empty_match(match):
        return match.empty()
else:
    def is_empty_match(match):
        return match is None
