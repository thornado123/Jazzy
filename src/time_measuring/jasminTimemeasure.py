import subprocess
import time
import pandas as pd
import sys
import os
DIR_PATH = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, f'{DIR_PATH}/..')
import jasminGenerator as JPG
import jasminPrettyPrint as JPP
import pickle

import signal
from contextlib import contextmanager

"""

    Program todo:
    
    1) Read a jasmin program and get its export function name (main or f0)
    2) Compile the jasmin file into test.s
    3) Change the name in the main.c file
    4) Compile the main.c file with the test.s file as input into test
    5) Run the ./test and read outputs 
    6) Save these outputs to a file on disk (pandas)

"""

class JasminTimeMeasurer:

    def __init__(self, jasmin_file, main_c_file):

        self.jasmin_file = jasmin_file
        self.jasmin_func_name = None
        self.main_c_file = main_c_file

    def get_jasmin_func_name(self):

        with open(self.jasmin_file, "r") as jazz_file:

            function_name = ""
            export_name = True

            while(export_name):

                new_line = jazz_file.readline()

                if "export" in new_line:

                    function_name = new_line.split("fn ")[1].split("(")[0]
                    export_name = False
            jazz_file.close()

        function_name.replace(" ", "")
        self.jasmin_func_name = function_name

    def change_name_in_main(self):

        with open(self.main_c_file, "r") as c_file:
            new_file_content = ""

            for line in c_file:
                stripped_line = line.strip()

                if "extern int64_t " in line:
                    old_func_name = line.split("int64_t ")[1].split("(")[0]
                    old_func_name.replace(" ", "")
                    stripped_line = stripped_line.replace(old_func_name, self.jasmin_func_name)
                elif "result " in line:
                    old_func_name = line.split("= ")[1].split("(")[0]
                    old_func_name.replace(" ", "")
                    stripped_line = stripped_line.replace(old_func_name, self.jasmin_func_name)

                new_file_content += stripped_line + "\n"

            c_file.close()

        writing_file = open(self.main_c_file, "w")
        writing_file.write(new_file_content)
        writing_file.close()

    def compile_jasmin(self):
        compiler_path = "/home/josefgharib/Desktop/Uni Projects/jasmin/compiler/./jasminc" #"/Users/thorjakobsen/GIT/jasmin/compiler/./jasminc"

        process = subprocess.Popen([compiler_path, self.jasmin_file, "-o", "jazz.s"],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        result = stderr.decode("utf-8")
        print("COMPILING JASMIN:", result)

    def compile_main_c(self):

        process = subprocess.Popen(["gcc", "-o", "test", "jazz.s", "main.c"],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        result = stderr.decode("utf-8")
        print("COMPILING C:", result)

    def run_main_c(self):

        process = subprocess.Popen(["./test"], stdout=subprocess.PIPE)
        start = time.time()
        time_start = time.time()
        result = [None] * 7
        current_value = 0
        current_time  = 0

        while True:
            output = process.stdout.readline()
            output = output.strip().decode("utf-8")

            if "DONE" in output:

                break

            elif "DIF" in output:
                print(">", output)
            else:

                output_list = output.split(" ")

                if "Fastest" in output:

                    result[2] = output_list[1]
                    result[4] = output_list[3]

                elif "Slowest" in output:

                    result[3] = output_list[1]
                    result[5] = output_list[3]

                elif "Values" in output:

                    current_time = time.time()
                    current_value = [output_list[2], output_list[4]]

                time_start = time.time()

            if time.time()-time_start > 30:

                print("STOPPED:", current_value, current_time)
                break

        result[6] = time.time() - start
        return result

nonterminating_seeds = []
@contextmanager
def timeout(time, seed):
    global nonterminating_seeds
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(time)
    try:
        yield
    except TimeoutError:
        print(f'Seed "{seed}" timed out!')
        nonterminating_seeds.append(seed)
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
def raise_timeout(signum, frame):
    raise TimeoutError
def main():
    start = sys.argv[1]
    end   = sys.argv[2]

    result_outputs = pd.DataFrame(columns=["Seed", "Time", "Fastest", "Slowest", "F_input", "S_input", "Total_running_time"])
    next = 0
    list_of_secure_programs = pickle.load(open(f"{DIR_PATH}/../../evaluation/list_of_secure_programs.p", "rb" ) )
    #nonterminating_seeds = [30068,30179,31542,33216]

    for i in range(int(start), int(end)):
        program_seed = list_of_secure_programs[i]
        # Timeout after 15 seconds
        with timeout(15,program_seed):
            print(program_seed)

            program_generator = JPG.JasminGenerator(program_seed)
            out = program_generator.get_program()
            out = [str(x) for x in out]
            out = "".join(out)
            out = JPP.jasmin_pretty_print(out)

            with open(f"{DIR_PATH}/test.jazz", "w") as file:
                file.write(out)
                file.close()

            jasmin_t = JasminTimeMeasurer("test.jazz", "main.c")
            jasmin_t.get_jasmin_func_name()
            jasmin_t.change_name_in_main()
            jasmin_t.compile_jasmin()
            jasmin_t.compile_main_c()
            result = jasmin_t.run_main_c()

            result[0] = list_of_secure_programs[i]
            result[1] = float(result[3]) - float(result[2])

            result_outputs.loc[next] = result
            next += 1

            print(next, "DONE")

    global nonterminating_seeds
    # Quick and dirty - last row will be multiple arrays of the samenon-terminating seeds.
    result_outputs.loc[next] = str(nonterminating_seeds)
    print(nonterminating_seeds)
    result_outputs.to_csv(f"{DIR_PATH}/../../evaluation/data/time_measure_results_" + start + "_" + end + ".csv")


if __name__ == '__main__':
    main()