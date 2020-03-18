#!/usr/bin/env python3
# coding=utf-8
from __future__ import print_function
import json
import os
import io
from datetime import datetime
import sys
import fontTables

TRANSLATION_CPP = "Translation.cpp"

try:
    to_unicode = unicode
except NameError:
    to_unicode = str


# Loading a single JSON file
def loadJson(fileName, skipFirstLine):
    with io.open(fileName, mode="r", encoding="utf-8") as f:
        if skipFirstLine:
            f.readline()

        obj = json.loads(f.read())

    return obj


# Reading all language translations into a dictionary by langCode
def readTranslations(jsonDir):
    langDict = {}

    # Read all translation files from the input dir
    for fileName in os.listdir(jsonDir):

        fileWithPath = os.path.join(jsonDir, fileName)
        lf = fileName.lower()

        # Read only translation_XX.json
        if lf.startswith("translation_") and lf.endswith(".json"):
            try:
                lang = loadJson(fileWithPath, False)
            except json.decoder.JSONDecodeError as e:
                print("Failed to decode " + lf)
                print(str(e))
                sys.exit(2)

            # Extract lang code from file name
            langCode = fileName[12:-5].upper()
            # ...and the one specified in the JSON file...
            try:
                langCodeFromJson = lang['languageCode']
            except KeyError:
                langCodeFromJson = "(missing)"

            # ...cause they should be the same!
            if langCode != langCodeFromJson:
                raise ValueError("Invalid languageCode " + langCodeFromJson +
                                 " in file " + fileName)

            langDict[langCode] = lang

    return langDict


def writeStart(f):
    f.write(
        to_unicode(
            """// WARNING: THIS FILE WAS AUTO GENERATED BY make_translation.py. PLEASE DO NOT EDIT.

#include "Translation.h"
#ifndef LANG
#define LANG_EN
#endif
"""))


def escapeC(s):
    return s.replace("\"", "\\\"")


def getConstants():
    # Extra constants that are used in the firmware that are shared across all languages
    consants = []
    consants.append(('SymbolPlus', '+'))
    consants.append(('SymbolMinus', '-'))
    consants.append(('SymbolSpace', ' '))
    consants.append(('SymbolDot', '.'))
    consants.append(('SymbolDegC', 'C'))
    consants.append(('SymbolDegF', 'F'))
    consants.append(('SymbolMinutes', 'M'))
    consants.append(('SymbolSeconds', 'S'))
    consants.append(('SymbolWatts', 'W'))
    consants.append(('SymbolVolts', 'V'))
    consants.append(('SymbolDC', 'DC'))
    consants.append(('SymbolCellCount', 'S'))
    consants.append(('SymbolVersionNumber', buildVersion))
    return consants


def getTipModelEnumTS80():
    constants = []
    constants.append("B02")
    constants.append("D25")
    constants.append("TS80")  # end of miniware
    constants.append("User")  # User
    return constants


def getTipModelEnumTS100():
    constants = []
    constants.append("B02")
    constants.append("D24")
    constants.append("BC2")
    constants.append(" C1")
    constants.append("TS100")  # end of miniware
    constants.append("BC2")
    constants.append("Hakko")  # end of hakko
    constants.append("User")
    return constants


def getDebugMenu():
    constants = []
    constants.append(datetime.today().strftime('%d-%m-%y'))
    constants.append("HW G ")
    constants.append("HW M ")
    constants.append("HW P ")
    constants.append("Time ")
    constants.append("Move ")
    constants.append("RTip ")
    constants.append("CTip ")
    constants.append("CHan ")
    constants.append("Vin  ")
    constants.append("PCB  ")  # PCB Version AKA IMU version
    return constants


def getLetterCounts(defs, lang):
    textList = []
    # iterate over all strings
    obj = lang['menuOptions']
    for mod in defs['menuOptions']:
        eid = mod['id']
        textList.append(obj[eid]['desc'])

    obj = lang['messages']
    for mod in defs['messages']:
        eid = mod['id']
        if eid not in obj:
            textList.append(mod['default'])
        else:
            textList.append(obj[eid])

    obj = lang['characters']

    for mod in defs['characters']:
        eid = mod['id']
        textList.append(obj[eid])

    obj = lang['menuOptions']
    for mod in defs['menuOptions']:
        eid = mod['id']
        if lang['menuDouble']:
            textList.append(obj[eid]['text2'][0])
            textList.append(obj[eid]['text2'][1])
        else:
            textList.append(obj[eid]['text'])

    obj = lang['menuGroups']
    for mod in defs['menuGroups']:
        eid = mod['id']
        textList.append(obj[eid]['text2'][0])
        textList.append(obj[eid]['text2'][1])

    obj = lang['menuGroups']
    for mod in defs['menuGroups']:
        eid = mod['id']
        textList.append(obj[eid]['desc'])
    constants = getConstants()
    for x in constants:
        textList.append(x[1])
    textList.extend(getTipModelEnumTS100())
    textList.extend(getTipModelEnumTS80())
    textList.extend(getDebugMenu())

    # collapse all strings down into the composite letters and store totals for these

    symbolCounts = {}
    for line in textList:
        line = line.replace('\n', '').replace('\r', '')
        line = line.replace('\\n', '').replace('\\r', '')
        if len(line):
            # print(line)
            for letter in line:
                symbolCounts[letter] = symbolCounts.get(letter, 0) + 1
    symbolCounts = sorted(
        symbolCounts.items(),
        key=lambda kv: (kv[1], kv[0]))  # swap to Big -> little sort order
    symbolCounts = list(map(lambda x: x[0], symbolCounts))
    symbolCounts.reverse()
    return symbolCounts


def getFontMapAndTable(textList):
    # the text list is sorted
    # allocate out these in their order as number codes
    symbolMap = {}
    symbolMap['\n'] = '\\x01'  # Force insert the newline char
    index = 2  # start at 2, as 0= null terminator,1 = new line
    forcedFirstSymbols = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    # enforce numbers are first
    for sym in forcedFirstSymbols:
        symbolMap[sym] = "\\x%0.2X" % index
        index = index + 1
    if len(textList) > (253 - len(forcedFirstSymbols)):
        print('Error, too many used symbols for this version')
        exit(1)
    print('Generating fonts for {} symbols'.format(len(textList)))

    for sym in textList:
        if sym not in symbolMap:
            symbolMap[sym] = "\\x%0.2X" % index
            index = index + 1
    # Get the font table
    fontTableStrings = []
    fontSmallTableStrings = []
    fontTable = fontTables.getFontMap()
    fontSmallTable = fontTables.getSmallFontMap()
    for sym in forcedFirstSymbols:
        if sym not in fontTable:
            print('Missing Large font element for {}'.format(sym))
            exit(1)
        fontLine = fontTable[sym]
        fontTableStrings.append(
            fontLine + "//{} -> {}".format(symbolMap[sym], sym))
        if sym not in fontSmallTable:
            print('Missing Small font element for {}'.format(sym))
            exit(1)
        fontLine = fontSmallTable[sym]
        fontSmallTableStrings.append(
            fontLine + "//{} -> {}".format(symbolMap[sym], sym))

    for sym in textList:
        if sym not in fontTable:
            print('Missing Large font element for {}'.format(sym))
            exit(1)
        if sym not in forcedFirstSymbols:
            fontLine = fontTable[sym]
            fontTableStrings.append(
                fontLine + "//{} -> {}".format(symbolMap[sym], sym))
            if sym not in fontSmallTable:
                print('Missing Small font element for {}'.format(sym))
                exit(1)
            fontLine = fontSmallTable[sym]
            fontSmallTableStrings.append(
                fontLine + "//{} -> {}".format(symbolMap[sym], sym))
    outputTable = "const uint8_t USER_FONT_12[] = {" + to_unicode("\n")
    for line in fontTableStrings:
        # join font table int one large string
        outputTable = outputTable + line + to_unicode("\n")
    outputTable = outputTable + "};" + to_unicode("\n")
    outputTable = outputTable + "const uint8_t USER_FONT_6x8[] = {" + to_unicode(
        "\n")
    for line in fontSmallTableStrings:
        # join font table int one large string
        outputTable = outputTable + line + to_unicode("\n")
    outputTable = outputTable + "};" + to_unicode("\n")
    return (outputTable, symbolMap)


def convStr(symbolConversionTable, text):
    # convert all of the symbols from the string into escapes for their content
    outputString = ""
    for c in text.replace('\\r', '').replace('\\n', '\n'):
        if c not in symbolConversionTable:
            print('Missing font definition for {}'.format(c))
        else:
            outputString = outputString + symbolConversionTable[c]
    return outputString


def writeLanguage(languageCode, defs, f):
    print("Generating block for " + languageCode)
    lang = langDict[languageCode]
    # Iterate over all of the text to build up the symbols & counts
    textList = getLetterCounts(defs, lang)
    # From the letter counts, need to make a symbol translator & write out the font
    (fontTableText, symbolConversionTable) = getFontMapAndTable(textList)

    f.write(to_unicode("\n#ifdef LANG_" + languageCode + "\n"))
    f.write(fontTableText)
    try:
        langName = lang['languageLocalName']
    except KeyError:
        langName = languageCode

    f.write(to_unicode("// ---- " + langName + " ----\n\n"))

    # ----- Writing SettingsDescriptions
    obj = lang['menuOptions']
    f.write(to_unicode("const char* SettingsDescriptions[] = {\n"))

    maxLen = 25
    for mod in defs['menuOptions']:
        eid = mod['id']
        if 'feature' in mod:
            f.write(to_unicode("#ifdef " + mod['feature'] + "\n"))
        f.write(to_unicode("  /* " + eid.ljust(maxLen)[:maxLen] + " */ "))
        f.write(
            to_unicode("\"" +
                       convStr(symbolConversionTable, (obj[eid]['desc'])) +
                       "\"," + "//{} \n".format(obj[eid]['desc'])))
        if 'feature' in mod:
            f.write(to_unicode("#endif\n"))

    f.write(to_unicode("};\n\n"))

    # ----- Writing Message strings

    obj = lang['messages']

    for mod in defs['messages']:
        eid = mod['id']
        sourceText = ""
        if 'default' in mod:
            sourceText = (mod['default'])
        if eid in obj:
            sourceText = (obj[eid])
        translatedText = convStr(symbolConversionTable, sourceText)
        f.write(
            to_unicode("const char* " + eid + " = \"" +
                       translatedText + "\";" + "//{} \n".format(sourceText.replace('\n', '_'))))

    f.write(to_unicode("\n"))

    # ----- Writing Characters

    obj = lang['characters']

    for mod in defs['characters']:
        eid = mod['id']
        f.write(
            to_unicode("const char* " + eid + " = \"" +
                       convStr(symbolConversionTable, obj[eid]) + "\";" + "//{} \n".format(obj[eid])))

    f.write(to_unicode("\n"))

    # Write out firmware constant options
    constants = getConstants()
    for x in constants:
        f.write(
            to_unicode("const char* " + x[0] + " = \"" +
                       convStr(symbolConversionTable, x[1]) + "\";" + "//{} \n".format(x[1])))

    f.write(to_unicode("\n"))
    # Write out tip model strings

    f.write(to_unicode("const char* TipModelStrings[] = {\n"))
    f.write(to_unicode("#ifdef MODEL_TS100\n"))
    for c in getTipModelEnumTS100():
        f.write(to_unicode("\t \"" + convStr(symbolConversionTable,
                                             c) + "\"," + "//{} \n".format(c)))
    f.write(to_unicode("#else\n"))
    for c in getTipModelEnumTS80():
        f.write(to_unicode("\t \"" + convStr(symbolConversionTable,
                                             c) + "\"," + "//{} \n".format(c)))
    f.write(to_unicode("#endif\n"))

    f.write(to_unicode("};\n\n"))

    # Debug Menu
    f.write(to_unicode("const char* DebugMenu[] = {\n"))

    for c in getDebugMenu():
        f.write(to_unicode("\t \"" + convStr(symbolConversionTable,
                                             c) + "\"," + "//{} \n".format(c)))
    f.write(to_unicode("};\n\n"))

    # ----- Menu Options

    # Menu type
    f.write(
        to_unicode(
            "const enum ShortNameType SettingsShortNameType = SHORT_NAME_" +
            ("DOUBLE" if lang['menuDouble'] else "SINGLE") + "_LINE;\n"))

    # ----- Writing SettingsDescriptions
    obj = lang['menuOptions']
    f.write(to_unicode("const char* SettingsShortNames[][2] = {\n"))

    maxLen = 25
    for mod in defs['menuOptions']:
        eid = mod['id']
        if 'feature' in mod:
            f.write(to_unicode("#ifdef " + mod['feature'] + "\n"))
        f.write(to_unicode("  /* " + eid.ljust(maxLen)[:maxLen] + " */ "))
        if lang['menuDouble']:
            f.write(
                to_unicode(
                    "{ \"" +
                    convStr(symbolConversionTable, (obj[eid]['text2'][0])) +
                    "\", \"" +
                    convStr(symbolConversionTable, (obj[eid]['text2'][1])) +
                    "\" }," + "//{} \n".format(obj[eid]['text2'])))
        else:
            f.write(
                to_unicode("{ \"" +
                           convStr(symbolConversionTable, (obj[eid]['text'])) +
                           "\" }," + "//{} \n".format(obj[eid]['text'])))
        if 'feature' in mod:
            f.write(to_unicode("#endif\n"))

    f.write(to_unicode("};\n\n"))

    # ----- Writing Menu Groups
    obj = lang['menuGroups']
    f.write(
        to_unicode("const char* SettingsMenuEntries[" + str(len(obj)) +
                   "] = {\n"))

    maxLen = 25
    for mod in defs['menuGroups']:
        eid = mod['id']
        f.write(to_unicode("  /* " + eid.ljust(maxLen)[:maxLen] + " */ "))
        f.write(
            to_unicode("\"" +
                       convStr(symbolConversionTable, (obj[eid]['text2'][0]) +
                               "\\n" + obj[eid]['text2'][1]) + "\"," + "//{} \n".format(obj[eid]['text2'])))

    f.write(to_unicode("};\n\n"))

    # ----- Writing Menu Groups Descriptions
    obj = lang['menuGroups']
    f.write(
        to_unicode("const char* SettingsMenuEntriesDescriptions[" +
                   str(len(obj)) + "] = {\n"))

    maxLen = 25
    for mod in defs['menuGroups']:
        eid = mod['id']
        f.write(to_unicode("  /* " + eid.ljust(maxLen)[:maxLen] + " */ "))
        f.write(
            to_unicode("\"" +
                       convStr(symbolConversionTable, (obj[eid]['desc'])) +
                       "\"," + "//{} \n".format(obj[eid]['desc'])))

    f.write(to_unicode("};\n\n"))

    # ----- Block end
    f.write(to_unicode("#endif\n"))


def read_opts():
    """ Reading input parameters
    First parameter = build version
    Second parameter = json directory
    Third parameter = target directory
    """
    if len(sys.argv) > 1:
        buildVersion = sys.argv[1]
    else:
        raise Exception("Could not get build version")
    if len(sys.argv) > 2:
        jsonDir = sys.argv[2]
    else:
        jsonDir = "."
    if len(sys.argv) > 3:
        outFile = sys.argv[3]
    else:
        outDir = os.path.relpath(jsonDir + "/../workspace/TS100/Core/Src")
        outFile = os.path.join(outDir, TRANSLATION_CPP)
    if len(sys.argv) > 4:
        raise Exception("Too many parameters!")
    return jsonDir, outFile, buildVersion


def orderOutput(langDict):
    # These languages go first
    mandatoryOrder = ['EN']

    # Then add all others in alphabetical order
    sortedKeys = sorted(langDict.keys())

    # Add the rest as they come
    for key in sortedKeys:
        if key not in mandatoryOrder:
            mandatoryOrder.append(key)

    return mandatoryOrder


def writeTarget(outFile, defs, langCodes):
    # Start writing the file
    with io.open(outFile, 'w', encoding='utf-8', newline="\n") as f:
        writeStart(f)

        for langCode in langCodes:
            writeLanguage(langCode, defs, f)


if __name__ == "__main__":
    try:
        jsonDir, outFile, buildVersion = read_opts()
    except:
        print("usage: make_translation.py {build version} {json dir} {cpp dir}")
        sys.exit(1)

    print("Build version string: " + buildVersion)
    print("Making " + outFile + " from " + jsonDir)

    langDict = readTranslations(jsonDir)
    defs = loadJson(os.path.join(jsonDir, "translations_def.js"), True)
    langCodes = orderOutput(langDict)
    writeTarget(outFile, defs, langCodes)

    print("Done")
