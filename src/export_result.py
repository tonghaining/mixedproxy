import os
import sys
from io import StringIO
import csv

import test_to_alloy

base_path = os.path.dirname(__file__) + "/.."
prefix = "litmus/PTX/"

with open(base_path + "/alloy/ptx.als", "r") as f:
    model = f.read()


class Capturing(list):
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stderr = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio
        del self._stdout


def prepare_csv_row(file_name, result):
    test_fild = prefix + file_name
    return [test_fild, int(result)]


def check_litmus(file):
    with open(base_path + "/dat3m_tests/" + file, "r") as f:
        test = f.read()
    try:
        with Capturing() as output:
            test_to_alloy.run_alloy(model=model, text=test, allow_failure=True)
    except Exception as e:
        print(f"{type(e).__name__} at line {e.__traceback__.tb_lineno} of {__file__}: {e}")
        return False
    return len(output) == 0


def main():
    dir_list = os.listdir(base_path + "/dat3m_tests/")
    dir_list.sort()
    rows = []
    for file in dir_list:
        if file[0] == "_":
            res = True
        else:
            res = check_litmus(file)
        rows.append(prepare_csv_row(file, res))
    with open('PTX-expected.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)


if __name__ == "__main__":
    main()
