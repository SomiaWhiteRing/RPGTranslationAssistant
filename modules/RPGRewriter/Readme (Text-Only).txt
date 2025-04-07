RPG Maker 200X Translation Assistant
Created by vgperson

This program is able to perform all kinds of tasks on data files from RPG Maker 2000/2003 games.
It's mainly intended for "developer" use, more specifically for translators of Japanese games (and translations into a variety of languages should now be possible).
It probably won't be very useful to the common player.

------------------------------------------------------------

@@@@@@@@@@@@@@@@@@@@ Usage Guides @@@@@@@@@@@@@@@@@@@@

These guides outline some of the primary uses for the program.
If you want to know what the program is good for in general, or if it can do what you want, continue reading. For details on individual functions, look further down at Program Functionality.

------------------------------------------------------------

=== I want to translate a game's script! ===

If you want to modify all the text in a game simply by editing text files, you can do so by exporting and importing StringScripts, a special format that focuses on text important to translation.

NOTE: If you're translating a language pair other than Japanese-English, you may need to do some extra steps regarding encoding, or scripts may export/import incorrectly.
Refer to the Text Encoding section further down.

1) Open the program. (Press Enter to advance past any messages about input.txt.)
Enter "T" ("Export editable StringScripts") and select the game's RPG_RT.lmt file. The program will then generate a StringScripts subfolder in the game folder.

2) Edit the scripts using your favorite text editor.
MapXXXX files contain strings from each map. In the Database folder are strings from each Database tab, as well as the Commons folder, which contains files for each Common Event.

* If you find you want extra information in the scripts for context, refer to UserSettings.txt (particularly the "StringScriptDetails" setting) to configure what you want included, then repeat step 1.
* For lots of little details on how StringScripts work, character limits, and more, refer to String Export/Import Notes further down.

3) Whenever you want to import the new text back into the game, open the program and enter "G" ("Import editable StringScripts").
This will load and update all files with the latest text from the scripts.

* Make sure to do this to get the data up-to-date before using things like the Translation Completeness Checker, as those functions check the data, not the text scripts!

------------------------------------------------------------

=== This game errors when I run it in such and such locale! ===
=== This game can't find files even though they exist! ===

The general cause of this is game resources having filenames that cause issues in certain locales.
When filenames have non-ASCII characters (basically anything that's not an English letter, number, or symbol on an English keyboard), then depending on the user's locale, this can lead to trouble when RPG Maker tries to load them.

Ideally, for maximum compatibility with any locale, all resource filenames should contain only ASCII characters.
So what this really means is...

=== I want to standardize resource filenames to be ASCII-only! ===

Simply renaming files manually will cause the game to error when it tries to reference their old names.
Thus, this program is equipped to change filenames in a way that keeps everything intact.

1) Open the program. If it says it can't find input.txt, that can be ignored for now.
Enter "F" ("Generate resource file list"). At the prompt, enter "Y" if you want only the filenames that can cause issues (usually all you need), or "N" if you want all filenames.
Select the game's RPG_RT.lmt file, and you'll get a file called filelist.txt in the RPGRewriter folder.

* Though not necessarily required, it's recommended you rename filelist.txt to something more specific, like the game's name. Otherwise, it will be overwritten by any other file list you generate.

2) Open up the generated text file. It should contain all the resource filenames in the appropriate folder categories, each one followed by a "___" placeholder.
Change all of the ___ lines to unique filenames; these should be ASCII-only translations of the original filenames above them.

* For more details about Replacement Lists and how to make them manually, refer to the Replacement List File Format futher down.

3) Open the program again.
If you named your file "input.txt" (or whatever the default is in User Settings), it will automatically load it. Otherwise, load it with the "A" function.
When loading a Replacement List, the program will warn if you anything is wrong with it, in which case you should make changes.

4) Once your Replacement List is correct and loaded, set your options to:
1. Rewriting
2. All Files
Enter "Z" ("Go!") and pick the RPG_RT.lmt file. This will rename all files and rewrite all data in the project according to the Replacement List.

* If any filenames you're trying to rename contain characters other than Japanese symbols or ASCII, they may fail to be changed in the data (even though the files themselves get renamed).
If this happens, try setting FilenameReadEncoding in UserSettings.txt appropriately, then try again.

4a) If it says upon completion that there were missing translations, enter "Y" to save a log file (default: log.txt) and check to see what they were.
Add them to your list and repeat step 4 as necessary.

5) That's it! But if you want to be extra sure there won't be any file errors, use Checking mode to check if all files exist where they should.

* NOTE: Save files from before you replaced filenames may error due to outdated references. Starting from a new game should work, however.
You can also use the program to "fix" old saves by loading them in Rewriting mode (Single File).

------------------------------------------------------------

=== A game I translated updated, so I want to update my translation to match! ===

This is best done by comparing versions of the game - either the updated version with your non-updated translation, or the source-language update with the previous source-language version.
So more generally, this means...

=== I want to compare versions of a game! ===

By extracting scripts from the different versions in specific ways, you can more easily compare their data and find the differences that matter for your purposes.

The first step in all of these examples is to set your options to:
1. Extracting
2. All Files
...and what you want to set the other options to depends on what you're doing.


< EXAMPLE 1: The original game made some typo fixes; how can I tell what was changed? >

You'll want to compare the previous version of the game and the updated version, covering only messages.

1) Set your Extraction options to extract All Files (2), Including Messages (3), and Skipping Actions (4).

Enter "Z" ("Go!") and pick the RPG_RT.lmt file for the old version. This will generate a MessageScripts subfolder in the game folder.

Enter "Z" again, and pick the RPG_RT.lmt file for the new version. This will again generate a MessageScripts subfolder in that folder.

2) Use a file comparison program (I suggest WinMerge) to compare the two MessageScripts folders.
The details may differ depending on what program you use, but you should see what maps/etc. had changes, and see exclusively the changes to message strings.


< EXAMPLE 2: I want to know what changed in this update so I can make the same changes to my translated version! >

You'll want to compare the previous version of the game and the updated version, covering all data.

1) Set your Extraction options to extract All Files (2), Including Messages (3), and Including Actions (4).

Enter "Z" ("Go!") and pick the RPG_RT.lmt file for the old version. This will generate a Scripts subfolder in the game folder.

Enter "Z" again, and pick the RPG_RT.lmt file for the new version. This will again generate a Scripts subfolder in that folder.

2) Use a file comparison program (I suggest WinMerge) to compare the two Scripts folders.
The details may differ depending on what program you use, but you should see what maps/etc. had changes, and what they were.

* Be aware that the differences can get confusing if pages are inserted or map events are rearranged.
Since event IDs and page numbers are included in the scripts, this can lead to large areas showing as changed. So even for relatively simple changes, it may not be obvious what actually happened.


< EXAMPLE 3: I want to check that my version matches the original in everything but text! (And that if anything else changed, it was intentional!) >

You'll want to compare the latest version of the original game and your translated version, covering only actions.

1) Set your Extraction options to extract All Files (2), Skipping Messages (3), Including Actions (4), and Using Numbers For Data (5).
(This setting for Option 5 helps cut down on file differences by not including data names, which may have been translated, every time something in the database is referenced.)

If filenames have been changed in your translation, you'll want to make sure the filenames match in both sets of scripts.
Thus, make sure the proper Replacement List is loaded (use the "A" function if necessary), and that Option 6 is set to Use Rewritten Strings.

Generally, I recommend leaving Option 7 as Blank Out Messages, which replaces each textbox command with "___".
However, Omit Messages Entirely, which outright skips over textbox commands, may be preferable if you don't care about textboxes being added or removed.

Enter "Z" ("Go!") and pick the RPG_RT.lmt file for the original version. This will generate an ActionScripts subfolder in the game folder.

Enter "Z" again, and pick the RPG_RT.lmt file for the translated version. This will again generate an ActionScripts subfolder in that folder.

2) Use a file comparison program (I suggest WinMerge) to compare the two ActionScripts folders.

The details may differ depending on what program you use, but you should see what maps/etc. had changes, and see exclusively the differences in non-message commands.
If there are differences that were intentional, I recommend making notes to keep track of what you can safely ignore in the future.

------------------------------------------------------------

@@@@@@@@@@@@@@@@@@@@ Program Functionality @@@@@@@@@@@@@@@@@@@@

This section goes into detail about individual functions the program can perform.

------------------------------------------------------------

===  Program Options ===

Type an option's number to toggle it. The numbered options determine what exactly the "[Z] Go!" function does and how. (The behavior of the other letter functions is generally independent of these.)

------------------------------------------------------------
GLOBAL OPTIONS  (Relevant to all modes)
------------------------------------------------------------

* 1. Mode (Extracting / Rewriting / Checking) *
The procedure you want to apply to the file(s).

Extracting will extract the desired contents of the file(s) as text.
For Single File, the file's contents will go on the clipboard. For All Files, text files for everything will be saved in a Scripts subfolder (or MessageScripts, or ActionScripts) in the game folder.
Note that the text files produced by Extracting mode are for reference only and cannot be "reinserted." If you want to do that, use the "Export/Import Editable StringScripts" function.

Rewriting will rewrite filename references and/or messages in the data file(s).
Ensuring that all filenames contain only ASCII characters is advantageous for letting players run the game in any locale. This mode allows you to automate the process of renaming files.
Rewriting a file will replace references to resource filenames and/or edit messages as according to the currently-loaded Replacement List. (See Replacement List File Format below for more details.)
If you choose to rewrite All Files, the program will automatically rename the files as well (the same thing the "V" function does - it's just performed as part of this for convenience).
If the program finds any filenames which still contain non-ASCII characters after completion, it will ask if you want to save a list of "missing translations" to a log file.

Checking can be used to check for various things.
If "Check Message Validity" is on, it will check that all messages (and choices, and other strings) are "valid," meaning they contain only ASCII characters.
If "Check File References" is on, it will go through the data and check that all file references actually exist in the correct resource folders.
If "Check Unused Files" is on, it will list any files that are present in the resource folders, but never actually get used by the game.
If "Check Unused Data Entries" is on, it will list any database entries that are filled out, but never actually get used by the game.
If "Check Line Lengths" is on, it will check the character count of all message lines against the number of characters that fit in the textbox.
If the program finds any issues in the selected categories, it will ask to save a log file of the issues it found.

------------------------------------------------------------

* 2. File Scope (Single File / All Files) *
Determines whether you want to run the program on a single file, or on every file in a game.
When you choose All Files, the Open File prompt will ask you to pick RPG_RT.lmt in the game folder.

------------------------------------------------------------

------------------------------------------------------------
EXTRACTING MODE OPTIONS (Only shown in Extracting Mode)
------------------------------------------------------------

* 3a. Include Messages (Including Messages / Skipping Messages) *
This determines whether or not the extracted text should include messages or not. The way in which messages are excluded can be customized with Option 7.

Excluding messages may be helpful if you're not interested in dialogue, only actions. (Action-only scripts are put in an "ActionScripts" folder instead of "Scripts.")
The Skipping Messages option will also turn other strings into "___" and omit names from the database script files.

------------------------------------------------------------

* 4a. Include Actions (Including Actions / Skipping Actions) *
This determines whether or not "actions" (anything but messages) will be included or not.
Excluding actions may be helpful if you're not interested in actions, only dialogue. (Message-only scripts are put in a "MessageScripts" folder instead of "Scripts.")

------------------------------------------------------------

* 5a. Use Data Names (Using Names / Using Numbers) *
When enabled, references to the database (i.e. "Hero #1") will use the name of that database entry (i.e. "Alex").
Using names is good for clarity. However, using numbers is helpful for script comparison purposes, as names will count as a "difference" every single time they're referenced.

------------------------------------------------------------

* 6a. Rewrite Strings (Keep Original / Use Rewritten) *
Keep Original Strings has strings stay exactly as they are in the output. Use Rewritten Strings, however, replaces strings using a Replacement List before putting them into the script.

Using this allows you to easily extract scripts from the original version of a game with filenames that theoretically match the translated version. You won't have to manually using Rewriting mode, and no actual files will be altered.
Matching the filenames in this way is highly advised if you're doing script comparison between versions.

------------------------------------------------------------

* 7a. Message Exclusion Type (Omit Messages Entirely / Blank Out Messages) *
Only applies when Skipping Messages.

Omit Messages Entirely will skip messages by simply leaving them out of the result files.
Blank Out Messages, on the other hand, changes each message into "___". This can be helpful if you want to know that a message is there, and how many separate textboxes there are, but don't care about their contents.

------------------------------------------------------------

------------------------------------------------------------
CHECKING MODE OPTIONS (Only shown in Checking Mode)
------------------------------------------------------------

* 3b. Check Message Validity (Check / Don't Check) *
Enabling this will include messages and other strings in the checking process. Any which contain non-ASCII characters will be put in the error log.
This is mostly useful for locating untranslated messages when doing a Japanese-to-English translation (by the logic of untranslated messages containing non-ASCII (Japanese) characters).

------------------------------------------------------------

* 4b. Check File References (Check / Don't Check) *
Enabling this will include filenames in the checking process. Any which cannot be found in the resource folders will be put in the error log.
This can help to track down references to now-deleted files, or to find out exactly what RTP files the game actually uses - it looks only in the game's own folders, not the RTP folders.

------------------------------------------------------------

* 5b. Check Unused Files (Check / Don't Check) *
Enabling this will do the reverse process of Check File References: it generates a list of files that exist in the resource folders, yet are never referenced.
This can be helpful for removing useless files to reduce filesize.

This check also notes the case of two or more files having the same name, but a different extension.
When this happens, RPG Maker chooses one over the other, which means one is left unused. For more information, see the Filename Extension Priority Reference further down.

If unused files are found, then after the logfile prompt, you'll be asked if you want to move unused files (including those unused by way of identical names) to their own subfolder.
This makes it easier to isolate and delete them if you have a lot of unused files.

------------------------------------------------------------

* 6b. Check Unused Data Entries (Check / Don't Check) *
Enabling this will check that all entries in the databases are used somewhere or another.
A "used" database entry is defined as one whose name is not blank, or otherwise differs in any way from the default "blank" settings.

Checking this can be helpful for the sake of determining file usage, as never-used database entries may be referring to files used nowhere else.
(The program does not automatically detect said files as unused, however.)

This check has some uncertainty to it, due to the fact that some databases can be referred to using a variable.
If such a reference is used, it cannot be said for certain whether any entry in that database is truly unused, so that will be noted in the log (unless there were concrete references to all entries, in which case there's no problem).

------------------------------------------------------------

* 7b. Check Line Lengths (Check / Don't Check) *
Enabling this will check each line of every message to see if it overflows past the edge of the textbox (meaning some characters are cut off), and logs lines that are too long.

It attempts to determine whether each message shows alongside a face or not, and uses this to know the maximum number of characters that will fit per line.
However, when conditional branches are involved, messages may in some cases be assumed as displaying without a face when they in fact do, resulting in an overflow.

------------------------------------------------------------

------------------------------------------------------------
EXECUTIVE FUNCTIONS
------------------------------------------------------------

* [Z] Go! *
Opens a file prompt to pick a file (either a specific data or save file, or RPG_RT.lmt for All Files mode), then runs the program with the options specified above.

------------------------------------------------------------

* [A] Load Replacement List File *
Type the filename of a Replacement List File in the local folder (without the ".txt" extension) to attempt to load that list.
Leaving the prompt blank will have it use the default given in User Settings (normally "input.txt").
You can use this to load Replacement List Files of any name, or reload a file if you've made changes.

When you start up the program, it will automatically try to load the default input file.
You should give your Replacement List File the default name (or vice versa) if you want it to automatically load on startup.

------------------------------------------------------------

* [Q] Translation Consistency Checker *
Pick the RPG_RT.lmt file for the original project, then the RPG_RT.lmt file for the translated project.
The program will then load in all the messages (and choices, and set-hero-names) from each project. After loading, it will compare the message lists for consistency.

It creates a "book of correct translations," matching original messages with translations. If it encounters the same original message more than once, it checks if it matches the prior translation, and logs it if there's a discrepancy.
Note that if the number of messages in any given page does not match between the projects, that page is skipped over entirely, as it's impossible for it to accurately determine how the messages "should" match up.
Also note that what it finds first and deems "correct" is based on the order of map and event numbers. If its "definition" is wrong, make sure to fix it at its origin, then run it again to find any other instances that were mistakenly assumed correct.

This function helps you ensure that the same messages are translated the same way everywhere. For further accuracy, it can also help to run the checker in the opposite direction (translated project to original).
Doing so will check whether the same translation is being used for multiple distinct original messages, identifying messages that were mistakenly given a copied translation of something else, when they should in fact be different.

------------------------------------------------------------

* [W] Translation Completeness Checker *
Pick the RPG_RT.lmt file for the original project, then the RPG_RT.lmt file for the translated project.

You'll be asked whether or not to use message replacements from the loaded Replacement List. If you enter "Y", replacements will be made on the original text before comparing to the translation. Otherwise, it will be kept as-is.
Accounting for message replacements is helpful if you have something like character names which you've replaced globally, yet don't want those replacements alone to "count" as the message being translated.
It will result in false positives if you've used MessagePart replacements to translate full messages, however.

Much like the Translation Consistency Checker, it loads the messages from each project and compares them. (Again, pages with non-matching numbers of messages are skipped over, since matches can't be accurately determined.)
It defines a "translated message" as one which has been changed from the original. So it logs messages which are "unchanged," and comes up with a percentage of changed messages.

------------------------------------------------------------

* [S] Compile Duplicate Message List *
Pick the RPG_RT.lmt file, and the program will generate a list of all messages throughout the game that appear in more than one place, which is put on the clipboard.
The number of occurrences for each message is included, and the most-repeated are at the top. This is most helpful for finding out what messages are very frequent and thus worth replacing globally to speed up translation.

------------------------------------------------------------

* [E] Extract Only Unique Messages *
Pick the RPG_RT.lmt file, and the program will extract message data from all maps, then put it on the clipboard.
However, it will only list each unique message once - if a message is duplicated elsewhere, any instances after the first are ignored.

You're also prompted on whether to include message sources. These tell you the locations where each message appears.
If you include all message sources ("Y" to the second prompt), the locations of all instances of the message will be listed. If you don't ("N" to the second prompt), only the first instance encountered will be given.

------------------------------------------------------------

* [C] Copy Map Tiles From One Project To Another *
Pick the RPG_RT.lmt file for the source project, then the RPG_RT.lmt file for the destination project.
The program will then load all the map tiles from the source project, and update the map tiles in the destination accordingly. This is a convenient way to get up-to-date with map layout changes.

------------------------------------------------------------

* [T] Export Editable StringScripts *
Pick the RPG_RT.lmt file, and the program will create a StringScripts folder with text files containing all strings from the game.
These scripts can be edited as you like, then re-inserted into the game with Import Editable StringScripts.
Note that you should generally only edit the contents of each command section; the program simply attempts to "paste" the contents into existing commands.

------------------------------------------------------------

* [G] Import Editable StringScripts *
Pick the RPG_RT.lmt file, and the program will load the files from the StringScripts folder (in the game folder, not the program folder) and insert those strings back into the game.
Refer to String Export/Import Notes further down for detailed information on how everything works.

------------------------------------------------------------

* ?. See Additional Functions / Back to Common Functions *
Toggles the list of functions on display. Generally, I put the more common functions in the default list and the niche ones in the additional list.
This is purely a display thing; all functions will work regardless of what's currently listed.

You can switch between the function lists by typing "?", or typing "/", or typing a space, or just pressing Enter with a blank prompt.

------------------------------------------------------------

* [D] Extract Map Tile Data *
Pick the RPG_RT.lmt file, and the program will extract tile data from all maps.
This creates text files for each map in a TileData folder that describe its tile layout. It's mostly for comparing whether the tiles match between versions of a game.

------------------------------------------------------------

* [R] Set Special Game Mode (For Extraction) *
Input the number of a game on the list to switch to that mode, or input anything else to return to the default mode.

These special modes are hardcoded, and aim to make improvements to the MessageScripts produced for specific games.
Generally, this means accounting for things besides messages that should also be included.

------------------------------------------------------------

* [F] Generate Resource File List *
Pick the RPG_RT.lmt file, and the program will generate a "preliminary" Replacement List File from the resource filenames and save it to filelist.txt.
All of the translations are left as "___", so it will not work immediately as a Replacement List File, but it will once you change the blanks to unique filenames.

------------------------------------------------------------

* [V] Rename Resource Files *
Pick the RPG_RT.lmt file, and the program will rename all resource files that need renaming according to the loaded Replacement List.
Note that you won't usually need to explictly do this - "Rewriting, All Files" includes this function.

------------------------------------------------------------

* [Y] Export Two-in-One Message Scripts *
Pick the RPG_RT.lmt file for the original project, then the RPG_RT.lmt file for the translated project.
The program will then load in all the messages (and choices, and set-hero-names) from each project, and create a combined "side-by-side" script which is put on the clipboard.
The two scripts are separated by tabs, so if you paste the result into Excel, it should automatically put the original text in one column and the translated text in another column.

The intent of this is for easy comparison between the original and translated texts. Normal message scripts are less suited for this purpose, as something as small as differing numbers of lines in a textbox causes misalignment.
However, note that if the translation has added or removed any textboxes, choices, or set-hero-names, the string matching will be off by one (or however many) for the remainder of that event page.
After all, the program has no way of knowing how messages should pair up, simply assuming it's one-to-one.

Note that at least currently, this function only covers map text. Common events and database strings may be added in the future.

------------------------------------------------------------

* [H] Copy Switch/Variable Names Between Projects *
Pick the RPG_RT.lmt file for the source project, then the RPG_RT.lmt file for the destination project.
The program will then load all the switch and variable names from the source project, and update the names in the destination accordingly.
You will be warned if the size of the switch/variable lists don't match between the projects - the size will not be changed automatically.

Switch and variable names have no gameplay effect, but are helpful to have for readability in the editor.

------------------------------------------------------------

* [N] Copy Action Command Values Between Projects *
Pick the RPG_RT.lmt file for the source project, then the RPG_RT.lmt file for the destination project.
The program will then load in select action commands from the source project, and update them in the destination accordingly.
You will be warned if the command counts don't match between the projects - the size will not be changed automatically.

The use cases for this are rather specific, but it can help if many values (i.e. durations of wait commands and others) get adjusted in an update.
(There may still be a lot of manual adding/removing of commands required, however.)

The current selection of commands is: Wait, Set Screen Tone, Flash Screen, Shake Screen, Pan Screen, Fade Out BGM. I may extend this function to have full customization in the future.

------------------------------------------------------------

* [X] Exit *
Exits the program.

------------------------------------------------------------

=== Save File Processing ===

Though not really considered "part of" a project (and thus left out of All Files), save files (SaveXX.lsd) can also be processed by the program in Single File mode.

Extracting mode extracts all the data contained within the save to the clipboard. This includes info like current map and position, hero stats, switch/variable values, and currently-active events.
Very little data is omitted here (the "verbose strings" setting changes nothing). All that's left out is the following: "leftover" animation data when no animation is playing, pictures that are not being used, and common events that are not actively running.
(Note: "[Default]" typically means that the string will, when loaded, become whatever is defined in the database. Hero names, for example, are only explicitly written in the save file if they are modified during the game itself, like if the player enters a name.)

Rewriting mode for save files presents a submenu with a variety of options for modifying the save.
You can change the values of switches and variables, change the locations of the party or vehicles, heal all characters, edit hero stats, change party lineup, change items, and set your current money.
If you have a Replacement List loaded, you can also apply it to the save file to replace outdated filename references.

Save files cannot be selected in Checking mode, as there is (at least currently) no meaning to that.

------------------------------------------------------------

=== User Settings ===

UserSettings.txt contains a variety of extra program settings you can configure.

User settings include customization of script formatting, word wrap settings (used with the Import Editable StringScripts functionality), encoding settings, and default options on startup.
The function of each setting and the options available for it are detailed within the file.

------------------------------------------------------------------------------------------------------------------------


@@@@@@@@@@@@@@@@@@@@ In-Depth Details @@@@@@@@@@@@@@@@@@@@

=== Replacement List File Format ===

Replacement List Files are generally a list of rules for translating a game's filenames, organized by folder (Picture, Sound, etc.), and can also contain rules applied to text strings.

IMPORTANT: Replacement List Files should be placed in the same folder as the program, and it's recommended you use Unicode encoding for them. (filelist.txt, and all other text files the program generates, are in Unicode.)

The first thing to do when writing a Replacement List File is to indicate the start of a section by putting one of the following on its own line:

***BACKDROP
***BATTLE
***BATTLE2
***BATTLECHARSET
***BATTLEWEAPON
***CHARSET
***CHIPSET
***FACESET
***FRAME
***GAMEOVER
***MONSTER
***MOVIE
***MUSIC
***PANORAMA
***PICTURE
***SOUND
***SYSTEM
***SYSTEM2
***TITLE

***MESSAGEALL
***MESSAGEPART
***MESSAGESTART
***OPTION
***NAME
***NICKNAME
***COMMENT

After that, make a list of filenames and their translations, or messages and their translations. An example Replacement List File:

***PICTURE
OriginalFileName1
TranslatedName1
OriginalFileName2
TranslatedName2
OriginalFileName3
TranslatedName3

***SOUND
OriginalFileName4
TranslatedName4
OriginalFileName5
TranslatedName5

***MESSAGEPART
[NameOfPersonTalking]
[NewNameOfPersonTalking]


* Notes *
- You should not include file extensions, because RPG Maker doesn't either. See "Filename Extension Priority Reference" for details, and for why you don't want two files with the same name.
- Every original should be matched with a translation (and a translation must contain only ASCII characters), so the program will warn you if a section appears to be "uneven" due to the presence of non-ASCII characters.
- Blank lines are completely ignored - not counted as originals or translations or section changes - so you can put them anywhere you wish to make things more readable.
- When you want to switch sections, use one of the *** section markers. You can use the same one more than once in a file, if you want; for example, have a ***PICTURE section, then ***PANORAMA, then switch back to do more ***PICTUREs.
- Warnings are given for duplicate originals (not harmful, but unnecessary), duplicate translations (in case of filenames, will likely result in multiple files trying to take the same name), and translations with characters invalid for a filename.
- The program will not be able to rename a file if the new name conflicts with an already-existing file. It will let you know if this occurs.


* Non-Filename Modes *
***BACKDROP through ***TITLE are all in reference to those resource folders. The other modes, however, act on various other strings that aren't resource filenames.

Note: All strings are case-sensitve. If you want to translate both "hot" and "Hot," you need to include both "hot -> cold" and "Hot -> Cold."

***MESSAGEALL / ***MESSAGEPART
Replaces all instances of a string if it is found in a message.
Example: Suppose the original string is "hot", and the translated string is "cold". If the message "It's actually hot, hot." is found, it will be rewritten to "It's actually cold, cold."

The difference between the two is that a MessageAll represents a full message translation, whereas a MessagePart is something that only covers part of a message.
This doesn't actually matter for most things, but it does in Completeness Checking: a message modified by a MessageAll is considered to be fully translated, while messages modified by MessageParts are not.

Basically, you should use MessagePart for things like commonly-occurring character names, and MessageAll for commonly-occurring complete textboxes.

***MESSAGESTART
Replaces a string only if it is found at the very beginning of a line (not necessarily the first line). In Completeness Checking, it is considered a "partial" translation the same way as a MessagePart.

***OPTION
Replaces options in a choice much like MessageAll/Part. These are left out in Completeness Checking on the assumption that choices translated with these are "done," so be sure to include all the options in any "choice sets" you cover.

***NAME
Replaces hero names in commands that involve them (Change Hero Name, Fork If Hero's Name = ___). It does not change the names of Heroes in the database.

***NICKNAME
The same as Name, but for hero nicknames (AKA titles, degrees, what have you). It does not change the nicknames of Heroes in the database.

***COMMENT
Replaces comment lines if they are an exact match.

------------------------------------------------------------

=== String Export/Import Notes ===

- The start of an event is marked with "**********EventX**********". The minimum required for the program to parse it is starting with * and containing a case-insensitive "*eventX*" (for a valid integer 0 or more).
- The start of a page is marked with "-----PageX-----". The minimum required for the program to parse it is starting with - and containing a case-insensitive "-pageX-" (for a valid integer 1 to 10).
- Each command begins with "#CommandName#". The minimum required for the program to parse it is starting with # and containing a case-insensitive "#commandname#" (for one of the supported commands).
- The end of each command's "content" is marked with a "##". The terminating line need only start with "##" to be parsed. (However, it's only actually relevant for Messages and Choices, since they use multiple lines.)
- Database scripts have "*****EntryX*****" instead of EventX, and names of fields in place of command names. Anything starting with a # will be considered a string field header (though of course, only valid names get used), and the line after it will be read as the contents.

- Anything after the above keywords (on the same line) is ignored, so you can use that space for comments. This includes the extra optional details you can choose to include for reference, such as event names and line numbers.
- What's actually crucial is the order of commands of the same type within each page. The first #Message# is inserted into the first instance of a message command in the page, the third #Choice# into the third instance of a choice command, etc.
- For common events, each individual event is just considered to be a single "page" in its own file, so *event* and -page- markers do nothing.
- For database scripts, since there is only one of each field per entry, the order they come in within the entry doesn't actually matter.
- You can put anything you want in the space between commands as long as it doesn't trip the *event*, -page-, or #command# checks.

- Events, pages, and commands will be skipped if not found in the input file. Choice commands will also be skipped if the choice counts don't match.
- Even if the number of commands doesn't match, insertion will still be done until the end of either the input or the data. In either case, the program will display a warning. If you get any warnings, you should check those areas to ensure things turned out correct.

- Most strings have a character limit, so when scripts are loaded, they'll be truncated by default. Choice options can have up to 32 characters. Hero names can have up to 12 characters. All database fields have their limits listed in [square brackets].
- Messages have a per-line character limit (50 characters with no face sprite, 38 with face sprite), and lines that go over will be truncated (default) or word-wrapped, depending on your settings in UserSettings.txt.
- The character limits given refer to the number of English characters allowed. Things like Japanese characters, which take up two bytes and are double the width, count as two "characters" toward the limit.
- For instance, a hero name (with a limit of 12) can be a maximum of 6 Japanese characters, or 3 Japanese characters + 6 English characters (3*2 + 6 = 12), or so on.
- If you don't want strings to be automatically truncated, you can disable this in UserSettings.txt.

- Message boxes can show a maximum of 4 lines, but if you want an extra text box immediately following an existing one, you can simply go past 4 lines, and the rest will show in one or more new boxes.
- Even if you re-export StringScripts, these boxes will be read as being all part of one big Message command, avoiding issues of mismatched command counts.
- This is possible because new boxes are internally specially-marked as being "extras." Be warned that if you edit them in the RPG Maker editor, this marking may be lost, causing confusion.
- You can also remove unwanted message boxes by putting "<<remove>>" (without quotes) as their content. Removed boxes show as blank commands in the editor, and re-export as Message commands marked for removal.

- The file OriginalStringsDB.json will be generated in the StringScripts folder on export if OriginalCommandStrings or OriginalDatabaseStrings are set to be included by UserSettings.txt, and it does not already exist.
- This file serves as a reference, containing all the strings from the game at the time of generation, and thus does not need to be edited and should generally be left alone.
- It is intended to store the game's original, untranslated strings, so if you've already made changes before generating it, it is recommended you generate StringScripts for the original, untranslated project and use that JSON file instead.
- If a matching string cannot be found in the JSON, it will display as "<Original string not found>".

------------------------------------------------------------

=== Text Encoding ===

By default, the program should be able to handle Japanese or English text just fine, with only a few exceptions (accented letters).
This is because the default encoding for reading and writing of data is Shift-JIS, which contains English and Japanese characters.
However, if you're doing a translation that involves languages besides those, you will likely have to switch the encoding.

The "main" read and write encodings can be changed in-program by entering "9" or "0" respectively, or you can change the startup defaults in User Settings.
A list of some (though not necessarily all) relevant codepage numbers:

932: Japanese/Basic English (Shift-JIS, default)
1252: Single-Byte Latin (Spanish)
1250: Latin Extended (contains accented characters, etc.)
1251: Cryllic
874: Thai
950: Traditional Chinese (Big5)
936: Simplified Chinese
949: Korean Hangul
65001: Unicode (definitely won't work with standard RPG_RT.exe)

The program defines all strings as one of three types, and you can specify what encodings to use when reading and writing each type.
In general, you probably only want to change the "Main" encodings, and leave the others alone so that those strings are left as-is.

The "Main" encodings cover all the strings you would want to edit in a translation: messages, hero names, etc. Every editable string included in a StringScript is using these encodings.
The "Filename" encodings cover filename references. If you're trying to rename files that use characters not in Shift-JIS (Chinese, for instance), make sure to change the filename read encoding accordingly, or they won't get properly replaced.
The "Misc." encodings cover strings that aren't "relevant" - they never appear in-game, so there's no real need to translate them. This includes map names, event names, troop names, and switch/variable names.

An example case: Say you're translating a Korean game to Thai, and want to do this using the Import/Export Editable StringScripts functions.
First, you need to set the main read encoding to 949 for Korean (enter "9", or change it in User Settings). Once set, the Export Editable StringScripts function should properly extract Korean text into Unicode scripts.
After doing translations in the scripts, set the main write enconding to 874 for Thai (enter "0", or change it in User Settings). Importing the scripts with this setting should write proper Thai into the files.
Characters not present in the write encoding (such as not-yet-translated text) will be written in a garbled way/become question marks/etc.
Don't worry, though: this shouldn't stop those strings from having properly-encoded translated strings imported over them later.

RPG Maker will use the encoding appropriate for the locale the player's system is running in, so you should make sure to note that to players.
Or, for more of a guarantee, you can have users run the game in EasyRPG Player, as it supports numerous encodings with no dependency on the user's locale.
(The encoding EasyRPG uses for each game is auto-detected based on the strings in the database. If it detects wrongly, you can manually define the codepage number in RPG_RT.ini.)

EasyRPG Player: https://easyrpg.org/
How to manually specify encoding for EasyRPG: https://wiki.easyrpg.org/user/player/special-features

------------------------------------------------------------------------------------------------------------------------

=== Filename Extension Priority Reference ===

When RPG Maker 2000/2003 looks for resource files, it looks for any file with the given name; file extensions are not stored in the data.
If multiple files share a name (but have a different extension), the leftmost extension in the corresponding list takes priority.

All image folders: .bmp > .png > .xyz
Music: .mid > .wav > .mp3 (if supported)
Sound: .wav only
Movies: .avi > .mpg

------------------------------------------------------------

=== Command Line Arguments ===

You can also run the program by passing arguments from the command line. The general format is:
RPGRewriter.exe "C:/Project/RPG_RT.lmt" [function] [settings]

Or, if using a function that involves two projects:
RPGRewriter.exe "C:/Project1/RPG_RT.lmt" "C:/Project2/RPG_RT.lmt" [function] [settings]

If you provide a directory instead of a file, it will try to look for an RPG_RT.lmt in that folder.


* Functions *
If you specify multiple functions, only the first one will be used.

-extract
Executes Extracting mode.

-rewrite
Executes Rewriting mode.

-check
Executes Checking mode.

-Q or -consistency
Executes consistency check. (Must provide two .lmt filenames.)

-W or -completeness [Y/N]
Executes completeness check. (Must provide two .lmt filenames.) Option specifies whether to use rewritten strings.

-S or -duplicate
Extracts duplicate messages. Result will be written to log file.

-E or -unique [0/1/2]
Extracts unique messages. Result will be written to log file. 0 = don't include source, 1 = include source of first instance, 2 = include all sources.

-D or -tiledata
Extracts tile data.

-C or -tilecopy
Executes tile copy. (Must provide two .lmt filenames.)

-R or -gamemode [0-3]
Sets game mode. 0 is normal, 1 is Ib, 2 is Walking on a Star Unknown, 3 is TOWER of HANOI.

-F or -filelist [Y/N]
Creates resource file list. Option specifies whether to include only non-ASCII filenames (Y) or all filenames (N).

-V or -filerename
Renames resource files based on loaded Replacement List.

-T or -export
Executes editable script export to StringScripts.

-G or -import
Executes editable script import from StringScripts.

-Y or -combo
Exports combined two-in-one message scripts. (Must provide two .lmt filenames.) Result will be written to log file.

-H or -svcopy
Executes switch/variable name copy. (Must provide two .lmt filenames.)

-N or -actcopy
Executes action command value copy. (Must provide two .lmt filenames.)


* Settings *
Unspecified settings will use the defaults from User Settings.

-single
Extracting/Rewriting/Checking will process only the one file. Extraction results will be written to log file.

-all
Extracting/Rewriting/Checking will process all files.

-messages [Y/N]
Sets message inclusion for Extracting.

-actions [Y/N]
Sets action inclusion for Extracting.

-datanames [Y/N]
Sets data name use for Extracting.

-stringreplace [Y/N]
Sets rewritten string use for Extracting.

-messageblank [Y/N]
Sets blanking of messages for Extracting.

-checkmessage [Y/N]
Enables message validation for Checking.

-checkfilename [Y/N]
Enables resource filename check for Checking.

-checkfileuse [Y/N]
Enables file use check for Checking.

-checkdatause [Y/N]
Enables database entry use check for Checking.

-checklength [Y/N]
Enables message length check for Checking.

-isolateunused [Y/N]
Enables isolation of unused files to "Unused" subfolders for Checking.

-verbose [Y/N]
Enables verbose strings for Extracting.

-nolimit [0-2]
Setting for character limits on database strings when using Import Editable StringScripts. 0 enforces limits, 1 does not, 2 enforces them except for battle strings that use placeholder codes.

-forceversion [0-3]
Forces a specific engine version when writing the LDB file. 0 doesn't change the version, 1 forces RPG Maker 2000 Japanese, 2 forces RPG Maker 2000 English, 3 forces RPG Maker 2003.

-log or -output [filename]
Sets log filename (relative to program folder, don't include extension). Useful to specify an output filename for functions that normally print to the clipboard.

-A or -input [filename]
Sets input filename (relative to program folder, don't include extension).

-readcode [codepage number]
-writecode [codepage number]
-filereadcode [codepage number]
-filewritecode [codepage number]
-miscreadcode [codepage number]
-miscwritecode [codepage number]
Sets read/write encoding for general strings, filenames, or miscellaneous strings.

------------------------------------------------------------

=== Special Thanks ===

EasyRPG's liblcf and EasyRPG Player were used as references.
Though I did initially figure out the file formats on my own, these helped a lot to confirm things and fill in gaps, especially for RPG Maker 2003 support and save files.
https://github.com/EasyRPG/