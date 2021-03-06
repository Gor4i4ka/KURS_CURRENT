from lxml import etree as et
from lxml import html as ht
from operator import itemgetter

import bs4
import re
import copy

# Internal imports
from projectLib.Common import save_list, load_list, juliet_shorten, find_in_juliet
from projectLib.Classes.ErrorInfo import ErrorInfo
from projectLib.Classes.FileInfo import FileInfo

class AnalyzerInfo:

    def __init__(self, analyzer_name="", info=[], info_type=""):
        self.analyzer_name = copy.deepcopy(analyzer_name)
        self.info = copy.deepcopy(info)
        self.info_type = copy.deepcopy(info_type)

    def append(self, element):
        self.info.append(copy.deepcopy(element))

    def remove(self, value):
        self.info.remove(value)

    def search_by_file(self, filename: str):
        if self.info_type == "FileInfo":
            for file in self.info:
                if file.file == filename:
                    return file
            return -1
        if self.info_type == "ErrorInfo":
            error_list = []
            for error in self.info:
                if error.file == filename:
                    error_list.append(error)

            if len(error_list) == 0:
                return -1
            return error_list
        print("NO SUCH info_type")
        return -2

    def mine_info(self, analyzer_name, xml_path, dir_list, defect_type_list, info_type="FileInfo"):

        # File check re expr
        re_expr = ""
        len_def = len(dir_list)
        for ind in range(len_def):
            re_expr += dir_list[ind] + "*"
            if ind != (len_def - 1):
                re_expr += "|.*"

        # Initial parsing
        manifest_tree = et.parse(xml_path, parser=et.XMLParser(remove_blank_text=True))
        manifest_root = ht.tostring(manifest_tree)
        manifest_soup = bs4.BeautifulSoup(manifest_root, features="lxml")

        # Choose the analyzer
        if analyzer_name == "juliet":
            self.analyzer_name = analyzer_name
            analyzer_output = self.__juliet_mine(re_expr, manifest_soup, defect_type_list)
        elif analyzer_name == "svace":
            self.analyzer_name = analyzer_name
            analyzer_output = self.__svace_mine(re_expr, manifest_soup, defect_type_list)
        else:
            print("NO SUCH ANALYZER")
            return -1

        # PostProcess analyzer's output
        analyzer_output.sort(key=itemgetter(0))

        if info_type == "ErrorInfo":
            self.__error_info_postproc(analyzer_output)
            return 0
        elif info_type == "FileInfo":
            self.__file_info_postproc(analyzer_output)
            return 0
        else:
            print("NO SUCH INFO MODE")
            return -1

    def save_info(self, path, info_ind):
        save_list(self.analyzer_name, path + "/inf_analyzer_name_ind" + str(info_ind) + ".data")
        save_list(self.info, path + "/inf_info_ind" + str(info_ind) + ".data")
        save_list(self.info_type, path + "/inf_info_type_ind" + str(info_ind) + ".data")
        return 0

    def load_info(self, path, info_ind):
        self.analyzer_name = load_list(path + "/inf_analyzer_name_ind" + str(info_ind) + ".data")
        self.info = load_list(path + "/inf_info_ind" + str(info_ind) + ".data")
        self.info_type = load_list(path + "/inf_info_type_ind" + str(info_ind) + ".data")
        return 0

    def print_info(self):
        if self.info_type == "FileInfo":

            for file_info in self.info:
                print(file_info)
                for error_info in file_info.errors:
                    print(error_info)
            return 0
        print("NO SUCH info_type")
        return -1

    def count_warnings(self):
        warning_list = []
        if self.info_type == "FileInfo":
            for file in self.info:
                for error in file:
                    in_list = False
                    for warning in warning_list:
                        if error.type == warning[0]:
                            warning[1] += 1
                            in_list = True
                            break
                    if not in_list:
                        warning_list.append([error.type, 1])

        return warning_list

    def __svace_mine(self, re_expr, manifest_soup, defect_type_list):
        result_list = []

        list_warn_sv = []
        loc_warn_sv = []

        found = manifest_soup.find_all("warninfo", attrs={"file": re.compile(re_expr)})
        foundloc = manifest_soup.find_all("warninfoex")

        for warnloc in foundloc:

            loc_warn = []
            loc_lines = []
            name = ""

            buffer_found = warnloc.find_all("roletraceinfo")

            for trace in buffer_found:
                if trace["role"] != "counter-example":
                    for locinf in trace.find_all("locinfo", attrs={"file": re.compile(re_expr)}):
                        if name == "":
                            name = locinf["file"]
                            loc_warn.append(name)
                        loc_lines.append(int(locinf["line"]))

            if len(loc_warn) > 0:
                loc_warn.append(loc_lines)
                loc_warn_sv.append(loc_warn)

        for warn in found:
            warning = [warn["file"], None, warn['warnclass']]
            list_warn_sv.append(warning)

        loc_warn_sv.sort(key=itemgetter(0))
        list_warn_sv.sort(key=itemgetter(0))
        for ind in range(len(list_warn_sv)):
            list_warn_sv[ind][1] = loc_warn_sv[ind][1]
            if (not defect_type_list) or (list_warn_sv[ind][2] in defect_type_list):
                result_list.append(list_warn_sv[ind])

        return result_list

    def __juliet_mine(self, re_expr, manifest_soup, defect_type_list):
        result_list = []
        testcases = manifest_soup.find_all("testcase")

        for case in testcases:

            testcase_list = []
            border = 0
            found = case.find_all(attrs={"path": re.compile(re_expr)})
            for file in found:

                has_flaw = False
                found_file = find_in_juliet(file["path"])
                if found_file == -1:
                    continue

                testcase_list.append([found_file, [], juliet_shorten(file["path"])])
                flaws = file.find_all("flaw")
                for flaw in flaws:
                    has_flaw = True
                    for ind in range(border, len(testcase_list)):
                        testcase_list[ind][1].append(int(flaw["line"]))
                if has_flaw:
                    border = len(testcase_list)

            for file in testcase_list:
                if len(file[1]):
                    result_list.append(file)

        return result_list

    def __file_info_postproc(self, analyzer_output):
        self.info_type = "FileInfo"

        for el in analyzer_output:

            if len(self.info) == 0 or el[0] != self.info[-1].file:
                self.append(FileInfo(file=el[0], errors=[ErrorInfo(lines=el[1], type=el[2])]))
            else:
                self.info[-1].append(ErrorInfo(lines=el[1], type=el[2]))

        return 0

    def __error_info_postproc(self, analyzer_output):
        self.info_type = "ErrorInfo"

        for el in analyzer_output:
            self.append(ErrorInfo(file=el[0], lines=el[1], type=el[2]))

        return 0

    def __str__(self):
        return self.analyzer_name + ": " + self.info_type

    def __getitem__(self, item):
        return self.info[item]

    def __setitem__(self, key, value):
        self.info[key] = value
        return 0