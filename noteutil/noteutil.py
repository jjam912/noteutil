from .notes import Note, Extension
from .comparisons import CompareOptions
from .errors import *
import os.path
from typing import List, Dict, Generator, Union, Tuple


def readlines(f) -> Generator[str, None, None]:
    """Splits a file into lines without the "\n" suffixes.

    Parameters
    ----------
    f: File

    Yields
    ------
    str
    """

    lines = f.read().split("\n")
    for line in lines:
        yield line.strip()


class NoteUtil:
    """NoteUtil is used for retrieving and manipulating Notes.
    It must be configured with a config file.

    Parameters
    ----------
    config_file : str
        The name of the config file that is used to set up this NoteUtil.

    Attributes
    ----------
    note_file: str
        The name of the file with notes, likely a text file.
    nu_file: str
        The same name of the file with notes, but with a .nu extension indicating NoteUtil modified.
    comments: str
        The prefix of lines that should be ignored in the note file.
    blocks: str
        The prefix and suffix of lines that mark the beginning and end of a block of notes (multi-line).
    separator: str
        A delimiter used to split Note lines into pairs (terms and definitions).
    notes : List[Note]
        All Notes created from the .nu file.
    heading_char : str
        If a Note is a heading, its content will start with this character.
    levels : int
        The number of headings.
    level_names : List[str]
        The general name of each group of headings.
    level_order : Dict[str, List[Note]]
        Mapped general names of headings to a list of notes that are headings that belong to that name.
    heading_names : List[str]
        The list of all heading names in chronological order.
    heading_order : List[Note]
        Chronological list of notes that are headings.
    category_names : List[str]
        The list of all category names in chronological order.
    category_prefixes : List[str]
        The list of all category prefixes in chronological order.
        zip(category_names, category_prefixes) gives correctly corresponding names and prefixes.
    categories : Dict[str, List[int]]
        Mapped category names to list of Notes.
    extension_names : List[str]
        List of all generic names of the extensions.
    extension_bounds : List[Tuple[str, str]]
        List of all (left bound, right bound) tuples that correspond to the extension names.
        zip(extension_names, extension_bounds) gives correctly corresponding names and bounds.
    with_extensions : List[Note]
        All Notes that have extensions.
    pairs : List[Note]
        All Notes that have terms and definitions.
    warnings : List[str]
        List of all of the warnings that occurred during the Note creation process.
    errors : List[str]
        List of all of the errors that occurred during the Note creation process.

    Raises
    ------
    NoteError
        If there were any severe problems during the Note creation process.
    """

    CONFIG_IGNORE_PREFIX = "#|"
    TEMPORARY_CONFIG_FILE = "noteutil_temporary_config.txt"

    def __init__(self, config_file: str, refresh: bool = True):
        self.notes = []
        self.config_file = config_file
        self.errors = []
        self._parse_config()
        self._read_config()
        if not os.path.exists(self.nu_file) or refresh:
            self._parse_notes()
        self._make_notes()
        if self.errors:
            raise NoteError("Errors\n"
                            "------\n"
                            "\t{0}\n"
                            "------".format("\n\t".join(self.errors)))
        self.save()

    @property
    def pairs(self) -> List[Note]:
        return list(filter(lambda n: n.is_pair(), self.notes))

    @property
    def level_order(self) -> Dict[str, List[Note]]:
        level_order = {name: [] for name in self.level_names}
        for note in self.heading_order:
            level_name = self.level_names[note.level - 1]
            level_order[level_name].append(note)
        return level_order

    @property
    def heading_order(self) -> List[Note]:
        return list(filter(lambda n: n.is_heading(), self.notes))

    @property
    def heading_names(self) -> List[str]:
        return list(map(lambda n: n.heading_name, self.heading_order))

    @property
    def categories(self) -> Dict[str, List[Note]]:
        categories = {name: [] for name in self.category_names}
        for note in self.notes:
            for category_name in note.category_names:
                categories[category_name].append(note)
        return categories

    @property
    def with_extensions(self) -> List[Note]:
        return list(filter(lambda n: n.has_extensions(), self.notes))

    def _parse_config(self) -> None:
        """Strips the config file of white space, empty lines, and comments.
        Detects unusual spacing and writes stripped contents into a temporary config file.
        """

        with open(self.config_file, mode="r", encoding="utf8") as f:
            raw_config = ""
            lines = f.readlines()
            for index, line in enumerate(lines):
                # If this line and the last line are blank, that means there are two blank lines.
                if line.startswith("\n") and index != 0 and lines[index - 1].startswith("\n"):
                    raise ExtraLine(index)
                # If this line is a blank line and the previous one was not a comment, there's an unexpected line.
                if line.startswith("\n") and index != 0 and lines[index - 1].strip().startswith(
                        self.CONFIG_IGNORE_PREFIX) is False:
                    raise UnexpectedLine(index)

                line = line.strip()

                # Remove any comments and leave only intended lines
                if line.startswith(self.CONFIG_IGNORE_PREFIX):
                    continue

                else:
                    raw_config += line + "\n"

        with open("noteutil_temporary_config.txt", mode="w", encoding="utf8") as f:
            f.write(raw_config)

    def _read_config(self) -> None:
        """Parses the config file into NoteUtil attributes."""

        with open(self.TEMPORARY_CONFIG_FILE, mode="r", encoding="utf8") as f:
            lines = f.readlines()
            if len(lines) < 13:
                raise IncorrectConfig(len(lines))

        with open(self.TEMPORARY_CONFIG_FILE, mode="r", encoding="utf8") as f:
            lines = readlines(f)

            # Read line by line to get each variable
            self.note_file = next(lines)
            self.nu_file = self.note_file.split(".")[0] + ".nu"
            self.comments = next(lines) or None
            self.blocks = next(lines) or None

            self.separator = next(lines) or None
            self._read_headings(lines)
            self._read_categories(lines)
            self._read_extensions(lines)

        os.remove(self.TEMPORARY_CONFIG_FILE)

    def _read_headings(self, lines):
        self.heading_char = next(lines) or None
        if self.heading_char is not None:
            self.levels = int(next(lines))
            self.level_names = []
            for _ in range(self.levels):
                self.level_names.append(next(lines))
        else:
            next(lines)
            next(lines)

    def _read_categories(self, lines):

        category_number = next(lines) or None
        if category_number:
            self.category_names = list()
            self.category_prefixes = list()
            for _ in range(int(category_number)):
                self.category_names.append(next(lines))
            for _ in range(int(category_number)):
                self.category_prefixes.append(next(lines))
        else:
            self.category_names = []
            self.category_prefixes = []
            next(lines)
            next(lines)

    def _read_extensions(self, lines):
        extension_number = next(lines) or None
        if extension_number:
            self.extension_names = list()
            self.extension_bounds = list()
            for _ in range(int(extension_number)):
                self.extension_names.append(next(lines))
            for _ in range(int(extension_number)):
                self.extension_bounds.append(tuple(next(lines).split()))
        else:
            self.extension_names = []
            self.extension_bounds = []
            next(lines)
            next(lines)

    def _parse_notes(self) -> None:
        """Strips the note file of empty lines, and comments.
        Writes the content to the .nu file.
        """

        try:
            open(self.note_file, mode="r", encoding="utf8").close()
        except FileNotFoundError:
            raise NoteFileNotFound(self.note_file)

        with open(self.note_file, mode="r", encoding="utf8") as f:
            raw_notes = ""
            for line in f.readlines():
                # Check for comments or empty line
                if self.comments is not None:
                    if line.strip().startswith(self.comments):
                        continue
                if line.strip() == "":
                    continue

                # Passed, add it to the raw notes
                raw_notes += line

        with open(self.nu_file, mode="w", encoding="utf8") as f:
            f.write(raw_notes)

    def _read_notes(self) -> Generator[str, None, None]:
        """Splits a file into lines without the "\n" suffixes.
        Continues a line if it starts with line_continue.

        Yields
        ------
        str
        """

        with open(self.nu_file, mode="r", encoding="utf8") as f:
            lines = f.read().split("\n")

            index = 0
            while index < len(lines):
                line = lines[index]
                if self.blocks is not None:
                    if line.strip().startswith(self.blocks):
                        line = line[len(self.blocks):]
                        index += 1
                        while index < len(lines):
                            line += "\n" + lines[index]
                            if lines[index].strip().endswith(self.blocks):
                                break
                            index += 1
                        line = line[:-1 * len(self.blocks)]
                if line != "":
                    yield line.strip()
                index += 1

    def _make_notes(self) -> None:
        """Parses the newly written .nu file and creates Notes in the order of Heading, Extensions, Pairs, and Notes.
        Adds all of the notes to self.notes.
        """

        for nindex, content in enumerate(self._read_notes()):
            try:
                note = self._make_note(content, nindex)
                self.notes.append(note)
            except NoteError as e:
                self.errors.append(e.args[0])

        # Headings are still missing their end_nindex:
        self._complete_headings()

    def _make_note(self, content, nindex):
        """This private version exists because Notes do not have their end_nindex yet and thus it can't be assigned,
        whereas in public use, end_nindexes and heading order have already been assigned."""
        kwargs = {}
        # The following 3 all modify content in some way:
        content = self._detect_headings(content, nindex, kwargs)
        content = self._detect_categories(content, kwargs)
        content = self._detect_extensions(content, kwargs)
        self._detect_pairs(content, kwargs)

        # Since content may have been modified, fix up heading_name
        if kwargs.get("heading_name", False):
            kwargs["heading_name"] = content
        return Note(self, content, nindex, **kwargs)

    def make_note(self, content, nindex):
        note = self._make_note(content, nindex)
        note.end_nindex = note.next_heading.nindex if note.next_heading else len(self.notes)
        self.insert(note, nindex)
        return note

    def _detect_headings(self, content, nindex, kwargs):
        if self.heading_char is not None:
            if content.startswith(self.heading_char):
                kwargs["heading_char"] = self.heading_char

                try:
                    previous_level = self.heading_order[-1].level
                except IndexError:
                    previous_level = 0
                kwargs["level"] = current_level = content.count(self.heading_char, 0, self.levels)
                kwargs["level_name"] = self.level_names[kwargs["level"] - 1]
                if current_level - previous_level > 1:
                    raise HeadingJump(content, previous_level, current_level)
                kwargs["heading"] = kwargs["heading_char"] * kwargs["level"]
                content = content[len(kwargs["heading"]):].lstrip()
                kwargs["heading_name"] = content
                if kwargs["heading_name"] in self.heading_names:
                    raise DuplicateHeading(kwargs["heading_name"])

                kwargs["begin_nindex"] = nindex + 1
        return content

    def _detect_categories(self, content, kwargs):
        if self.category_names is not None and self.category_prefixes is not None:
            kwargs["category_names"] = []
            kwargs["category_prefixes"] = []
            for name, prefix in zip(self.category_names, self.category_prefixes):
                if content.startswith(prefix):
                    kwargs["category_names"].append(name)
                    kwargs["category_prefixes"].append(prefix)
                    content = content[len(prefix):].lstrip()
        return content

    def _detect_extensions(self, content, kwargs):
        if self.extension_names is not None and self.extension_bounds is not None:
            kwargs["extensions"] = []
            kwargs["extension_bounds"] = []
            kwargs["extension_names"] = []
            for name, bounds in zip(self.extension_names, self.extension_bounds):
                lbound, rbound = bounds
                kwargs["extension_bounds"].append(tuple([lbound, rbound]))
                while lbound in content:
                    lindex = content.index(lbound) + len(lbound)
                    if rbound in content[lindex:]:
                        rindex = content.index(rbound, lindex)
                        kwargs["extensions"].append(
                            Extension(content[lindex:rindex].strip(), name, lbound, rbound))
                        if name not in kwargs["extension_names"]:
                            kwargs["extension_names"].append(name)

                        content = content[:lindex - len(lbound)].strip() + " " + content[rindex + len(rbound):].strip()
                    else:
                        raise MissingBound(content, lbound, rbound)
        return content

    def _detect_pairs(self, content, kwargs):
        if self.separator is not None:
            if self.separator in content:  # Line is a pair, add additional parameters
                if len(content.split(self.separator)) > 2:
                    raise ExtraSeparator(content)

                kwargs["term"] = content.split(self.separator)[0].strip()
                if kwargs["term"] in map(lambda n: n.term, self.pairs):
                    raise DuplicateTerm(kwargs["term"])

                kwargs["definition"] = content.split(self.separator)[1].strip()
                if kwargs["definition"] == "":
                    raise NoDefinition(content)

                kwargs["separator"] = self.separator

    def _complete_headings(self):
        if self.heading_char is not None:
            headings_by_level = list(self.level_order.values())
            heading_order = self.heading_order

            for headings in headings_by_level:
                for i in range(len(headings)):
                    heading = headings[i]
                    level_index = i + 1     # The next heading index at the same level
                    order_index = heading_order.index(heading) + 1    # The next heading index in heading order

                    while order_index != len(heading_order) and \
                            heading_order[order_index].level > heading.level:
                        order_index += 1

                    if level_index == len(headings):
                        level_nindex = len(self.notes)
                    else:
                        level_nindex = headings[level_index].nindex

                    if order_index == len(heading_order):
                        order_nindex = len(self.notes)
                    else:
                        order_nindex = heading_order[order_index].nindex

                    if level_nindex < order_nindex:
                        end_nindex = level_nindex
                    else:
                        end_nindex = order_nindex

                    heading.end_nindex = end_nindex

    def get(self, **kwargs) -> Union[None, Note]:
        """Retrieves a Note with attributes equal to passed keyword args.

        Parameters
        ----------
        kwargs
            Keys are attribute names and Values are values you are looking for in those attributes.

        Other Parameters
        ----------------
        compare
            If one of the keys of kwargs is compare, comparisons will be used with the value of this key.
            The custom compare must accept the parameters: Note, **kwargs

        Returns
        -------
        Note or None
            If a Note is found to have the passed attributes.
            If no Note is found.
        """

        if not kwargs:
            return None

        compare = kwargs.pop("compare") if kwargs.get("compare", False) else CompareOptions.EQUALS

        for note in self.notes:
            if compare(note, **kwargs):
                return note
        return None

    def get_list(self, **kwargs) -> Union[None, List[Note]]:
        """Retrieves all Notes with attributes equal to passed keyword args and stores them in a List.

        Parameters
        ----------
        kwargs
            Keys are attribute names and Values are values you are looking for in those attributes.

        Other Parameters
        ----------------
        compare
            If one of the keys of kwargs is compare, comparisons will be used with the value of this key.
            The custom compare must accept the parameters: Note, **kwargs

        Returns
        -------
        List[Note] or None
            If a Notes are found to have the passed attributes.
            If no Notes are found.
        """

        if not kwargs:
            return None
        notes = []
        compare = kwargs.pop("compare") if kwargs.get("compare", False) else CompareOptions.EQUALS

        for note in self.notes:
            if compare(note, **kwargs):
                notes.append(note)
        return notes if notes else None

    def iget(self, **kwargs) -> Union[None, Note]:
        """Retrieves a Note without attributes equal to passed keyword args.
        "Inverted"-get

        Parameters
        ----------
        kwargs
            Keys are attribute names and Values are values you are looking for in those attributes.

        Other Parameters
        ----------------
        compare
            If one of the keys of kwargs is compare, comparisons will be used with the value of this key.
            The custom compare must accept the parameters: Note, **kwargs

        Returns
        -------
        Note or None
            If a Note is found to not have the passed attributes.
            If no Note is found.
        """

        if not kwargs:
            return None

        compare = kwargs.pop("compare") if kwargs.get("compare", False) else CompareOptions.EQUALS

        for note in self.notes:
            if not compare(note, **kwargs):
                return note
        return None

    def iget_list(self, **kwargs) -> Union[None, List[Note]]:
        """Retrieves all Notes without attributes equal to passed keyword args and stores them in a List.
        "Inverted"-get_list

        Parameters
        ----------
        kwargs
            Keys are attribute names and Values are values you are looking for in those attributes.

        Other Parameters
        ----------------
        compare
            If one of the keys of kwargs is compare, comparisons will be used with the value of this key.
            The custom compare must accept the parameters: Note, **kwargs

        Returns
        -------
        List[Note] or None
            If a Notes are found to not have the passed attributes.
            If no Notes are found.
        """

        if not kwargs:
            return None

        notes = []
        compare = kwargs.pop("compare") if kwargs.get("compare", False) else CompareOptions.EQUALS

        for note in self.notes:
            if not compare(note, **kwargs):
                notes.append(note)
        return notes if notes else None

    def edit(self, nindex: int, content: str) -> Note:
        """Given a Note, edit its content.
        This can have many side effects:
            1. Changes to heading.
            2. Changes to heading_name.
            3. Changes to categories.
            4. Changes to extensions.
            5. Changes to whether the Note is a pair.
            6. Changes to term, definition, and separator.

        Parameters
        ----------
        content : str
            The new content that the Note should have.
        nindex : int
            The note index of the Note you want to modify.

        Returns
        -------
        Note
            The modified note.

        Raises
        ------
        NoteError
        HeadingJump
        MissingBound
        ExtraSeparator
        DuplicateTerm
        NoDefinition
        """

        content = content.strip()
        old_note = self.notes.pop(nindex)
        try:
            self.make_note(content, nindex)
        except NoteError:
            self.notes.insert(nindex, old_note)
            raise
        return self.notes[nindex]

    def insert(self, note, nindex):
        """Creates and inserts a Note at the given nindex.

        Parameters
        ----------
        note : Note
            The Note to insert at position nindex.
        nindex : int
            The note index of the Note to be inserted.

        Returns
        -------
        None
        """

        if not 0 <= nindex <= len(self.notes):
            raise NindexError(nindex)

        self.notes.insert(nindex, note)
        if note.previous_heading is not None and note.previous_heading.end_nindex is not None:
            note.previous_heading.end_nindex += 1

        for i in range(nindex + 1, len(self.notes)):
            n = self.notes[i]
            n.nindex += 1
            if n.is_heading():
                n.begin_nindex = n.nindex + 1
        self._complete_headings()

    def delete(self, nindex) -> None:
        """Deletes a Note at the given nindex.

        Parameters
        ----------
        nindex : int
            The note index of the Note to be deleted.

        Returns
        -------
        None
        """

        if not 0 <= nindex < len(self.notes):
            raise NindexError(nindex)

        n = self.notes[nindex]
        if n.previous_heading is not None and n.previous_heading.end_nindex is not None:
            n.previous_heading.end_nindex -= 1
        del self.notes[nindex]

        for i in range(nindex, len(self.notes)):
            note = self.notes[i]
            note.nindex -= 1
            if note.is_heading():
                note.begin_nindex -= 1
        self._complete_headings()

    def save(self, override_notes: bool = False) -> None:
        """Writes all of the Notes back into what they were when they were being parsed into a .nu file.

        If any changes to the Notes were made, they will be written here as well.

        Returns
        -------
        None
        """

        raw_notes = "\n".join(list(map(lambda n: n.rcontent, self.notes)))
        with open(self.nu_file, mode="w", encoding="utf8") as f:
            f.write(raw_notes)
        if override_notes:
            with open(self.note_file, mode="w", encoding="utf8") as f:
                f.write(raw_notes)

    def load(self) -> None:
        """Re-parses the .nu file, reverting any changes that could have been made to NoteUtil during use.

        Returns
        -------
        None
        """

        self.__init__(self.config_file, refresh=False)

    def refresh(self) -> None:
        """Re-initializes the NoteUtil from the note file instead of the .nu file.
        This is used to match a new or updated note file.

        Returns
        -------
        None
        """

        self.__init__(self.config_file, refresh=True)
















