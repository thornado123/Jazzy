"""

    The Jasmin program generator is a deterministic Jasmin source program generator
    that take a seed token and generates a program with offset in this token.


    Methods:

        __init__:

            - set the current seed value

        getProgram:

            - given a seed value return a valid Jasmin program


    Jasmin BNF:

    TYPES:

    <ptype>     ::= T_BOOL | T_INT | <utype> | <utype><brackets <pexpr>>
    <utype>     ::= T_U8 | T_U16 | T_U32 | T_U64 | T_U128 | T_U256


    EXPRESSIONS:

    <pexpr>     ::= <var> | <var><brackets<pexpr>> | TRUE | FALSE | INT | [<parens<ptype>>]<brackets(<var>+<pexpr>)>
                | <peop1><pexpr> | <pexpr><peop2><pexpr> | <parens<pexpr>> | <var><parens_tuple<pexpr>>
                | <prim><parens_tuple<pexpr>>

    <ident>     ::= NID
    <var>       ::= <ident>
    <prim>      ::= #<ident>

    <peop1>     ::= ! | -
    <peop2>     ::= + | - | * | && | PIPEPIPE | & | PIPE | ^ | << | >> | >>s | == | != | < | <= | > | >= | <s | <=s | >s
                | >=s

    INSTRUCTIONS:

    <pinstr>    ::= ARRAYINIT ⟨parens⟨var⟩⟩ ;
                | ⟨tuple1⟨plvalue⟩⟩ ⟨peqop⟩ ⟨pexpr⟩ [IF ⟨pexpr⟩] ; | ⟨var⟩ ⟨parens_tuple⟨pexpr⟩⟩ ;
                | IF ⟨pexpr⟩ ⟨pblock⟩
                | IF ⟨pexpr⟩ ⟨pblock⟩ ELSE ⟨pblock⟩
                | FOR ⟨var⟩ = ⟨pexpr⟩ TO ⟨pexpr⟩ ⟨pblock⟩
                | FOR ⟨var⟩ = ⟨pexpr⟩ DOWNTO ⟨pexpr⟩ ⟨pblock⟩ | WHILE [⟨pblock⟩] ⟨parens⟨pexpr⟩⟩ [⟨pblock⟩]

    <pblock>    ::= ⟨braces⟨pinstr⟩*⟩

    <peqop>     ::= =
                | += | -= | *=
                | >>= |>>s= |<<=
                | &= |^= | PIPEEQ

    <plvalue>   ::= UNDERSCORE | <var> | <var> <brackets<pexpr>> | [<parens<ptype>>]<brackets(<var> + <pexpr>)>

    FUNCTIONS:

    <pfunbody>  ::= LBRACE (⟨pvardecl⟩ ;)∗ ⟨pinstr⟩∗ [RETURN ⟨tuple⟨var⟩⟩ ;] RBRACE

    <storage>   ::= REG | STACK | INLINE

    <stor_type> ::= <storage><ptype>
    <pvardecl>  ::= <stor_type><var>


    GLOBAL DECLARATIONS:

    <module>    ::= <top> * EOF | error
    <top>       ::= <pfundef> | <pparam> | <pglobal>
    <call_conv> ::= EXPORT | INLINE //Inline is default
    <pfundef>   ::= [<call_conv>]FN <ident> <parens_tuple(<stor_type><var>)>[-><tuple<stor_type>>]<pfunbody>
    <pparam>    ::= PARAM <ptype><ident> = <pexpr>;
    <pglobal>   ::= <ident> = <pexpr>;

"""

import numpy as np
from datetime import datetime

import jasminDistribution as JD
from jasminNonterminalAndTokens import Nonterminals as JN
from jasminScopes import Scopes as JS
from jasminTypes import JasminTypes as JT


class JasminGenerator:

    def __init__(self, program_seed):

        self.seed               = program_seed
        self.action_global      = JD.GlobalDeclarations(self.seed)
        self.action_types       = JD.Types(self.seed)
        self.action_functions   = JD.Functions(self.seed)
        self.action_expressions = JD.Expressions(self.seed)
        self.action_instructions= JD.Instructions(self.seed)

        self.function_return    = False
        self.return_types       = []

        self.variable_types     = {}
        self.variables_of_type  = {}
        self.variables_storage  = {}

        #If a variable is used and it is not in ..._assigned then its added to ..._used_before...
        self.variables_input    = []
        self.variables_assigned = []
        self.variables_used_before_assignment = []

        self.variables = {

            JS.Variables    : [],
            JS.Arrays       : [],
            JS.Function_name: [],
            JS.Decl         : []

        }

        np.random.seed(self.seed)

    def get_program(self):

        program_info = ["// Program seed: ", str(self.seed), "\n", "// Generated by JasminFuzzer on ",
                   str(datetime.now()), " \n\n"]

        program = []

        amount_of_global_decls = 1 # self.action_prop(self.seed, "global")

        for _ in range(amount_of_global_decls):

            program += self.global_declarations()

        """
        
            Removing unused variables
        
        """

        program = self.remove_unused_variables(program)

        """
        
            Add missing call structure
        
        """

        program = self.add_outer(program)

        """

            Adding string rep. of the different types

        """

        program = self.clean_types(program)

        return program_info + program

    def clean_types(self, program_list):

        for i in range(len(program_list)):

            part = program_list[i]

            if isinstance(part, JT):

                program_list[i] = part.name.lower()

        return program_list

    def add_outer(self, program_list):

        input_type   = None
        output_type  = None
        extras       = []
        target_types = [JT.BOOL, JT.INT]

        if len(program_list) > 6 and program_list[6] != "":

            input_type = self.variable_types[self.variables_input[0]]

        if len(program_list) > 3 and self.function_return:

            output_type = self.variable_types[program_list[-3]]

        if input_type is not None or output_type is not None or (len(program_list) > 3 and program_list[-3] in self.variables[JS.Arrays]):

            extras = ["reg u64 final;\n"]

            if input_type is not None and output_type is not None:

                if input_type == JT.BOOL:

                    extras += ["reg bool b1;\n",
                               "_, _, _, _, b1 = #CMP(input, 42);\n",
                               "result = f0(b1);\n"
                               ]

                elif input_type == JT.INT:

                    extras += ["inline int b1;\n",
                               "b1 = ", np.random.randint(0, 1000), ";\n",
                               "result = f0(b1);\n"
                               ]

                elif input_type == JT.U64:

                    if self.variables_input[0] in self.variables[JS.Arrays]:

                        extras += [ "reg u64[5] b1;\n",
                                    "b1[1] = input;\n"
                                    "result = f0(b1);\n"
                                ]

                    else:

                        extras += [
                                    "result = f0(input);\n"
                                   ]

                else:

                    if self.variables_input[0] in self.variables[JS.Arrays]:

                        extras += [ "reg ", input_type, "[5] b1;\n",
                                    "b1[1] = ", np.random.randint(0, 1000),";\n",
                                    "result = f0(b1);\n"
                                ]

                    else:

                        extras += ["reg ", input_type, " b1;\n",
                                   "b1 = ", np.random.randint(0, 1000), ";\n",
                                   "result = f0(b1);\n"
                                   ]

            elif input_type in target_types:

                if input_type == JT.BOOL:
                    extras += ["reg bool b1;\n",
                               "_, _, _, _, b1 = #CMP(input, 42);\n",
                               "f0(b1);\n"
                               ]

                if input_type == JT.INT:

                    extras += ["inline int b1;\n",
                               "b1 = ", np.random.randint(0, 1000), ";\n",
                               "f0(b1);\n"
                               ]

            if output_type is not None:

                if input_type is None:

                    extras += ["result = f0();\n"]

                if output_type == JT.BOOL:

                    extras = ["reg bool result;\n"] + extras
                    extras += ["if result {\n",
                               "input += 42;\n",
                               "}"
                               ]

                elif output_type == JT.INT:

                    extras = ["inline int result;\n"] + extras
                    extras += ["final = result;\n","input += final;"]

                elif program_list[-3] in self.variables[JS.Arrays]:

                    extras = ["reg ", output_type, "[5] result;\n"] + extras
                    extras += ["if result[1] > 42 {\n",
                               "input += 1;\n",
                               "}"
                               ]

                else:

                    extras = ["reg ", output_type, " result;\n"] + extras
                    extras += ["if result > 42 {\n",
                                   "input += 42;\n",
                                   "}"
                                   ]

            if not (input_type == JT.U64 and output_type == JT.U64 and program_list[-3] not in self.variables[JS.Arrays]\
                    and self.variables_input[0] not in self.variables[JS.Arrays]):

                extras = ["export fn main_jazz(reg u64 input) -> reg u64 {\n"] + extras + ["\n", "final = input;\n", "return final;\n}"]
                program_list[0] = "inline"
                program_list = program_list + ["\n"] + extras

        return program_list

    def remove_unused_variables(self, program_list):

        for var in self.variable_types.keys():

            if program_list.count(var) == 1:
                index = program_list.index(var)

                if var == "v0":

                    program_list[index]     = ""
                    program_list[index - 1] = ""
                    program_list[index - 2] = ""
                    program_list[index - 3] = ""
                    program_list[index - 4] = ""

                    if var in self.variables[JS.Arrays]:
                        program_list[index-5] = ""
                else:

                    program_list[index + 1] = ""
                    program_list[index]     = ""
                    program_list[index - 1] = ""
                    program_list[index - 2] = ""
                    program_list[index - 3] = ""
                    program_list[index - 4] = ""

                    if var in self.variables[JS.Arrays]:

                        program_list[index-5] = ""

        return program_list

    def get_variable(self, scope, evaluation_type=None):

        if scope == JS.Arrays:

            types_array = [x for x in self.variables[JS.Arrays] if self.variable_types[x] == evaluation_type]

            if len(types_array) == 0:
                return None

            else:

                result = np.random.choice(types_array, 1, replace=False)
                return result[0]

        if scope == JS.Variables:

            index = np.random.choice(self.variables[JS.Variables], 1, replace=False)
            return index[0]

        if scope == JS.Decl:

            new_var = "v"

            if len(self.variables[JS.Variables]) == 0:

                self.variables[JS.Variables] = [new_var + "0"]
                return new_var + "0"

            else:

                new_var = new_var + str(len(self.variables[JS.Variables]))
                self.variables[JS.Variables].append(new_var)

                return new_var

        if scope == JS.Function_name:

            if self.variables[JS.Function_name] == 0:

                new_func = "f0"
                self.variables[JS.Function_name] = [new_func]
                return new_func

            else:

                new_func = "f" + str(len(self.variables[JS.Function_name]))
                self.variables[JS.Function_name].append(new_func)

                return new_func

        else:

            if scope in self.variables_of_type:

                if len(self.variables_of_type[scope]) > 1 and isinstance(self.variables_of_type[scope], list):

                    return np.random.choice(self.variables_of_type[scope], 1, replace=False)[0]

                else:

                    return self.variables_of_type[scope][0]

            else:

                return None

    """
    
        Global decl. 
        
        Is at depth 0
        
    """

    def global_declarations(self, action=None):

        if action is None:

            action = self.action_global.get_action()
            return self.global_declarations(action=action)

        elif action == JN.Module:

            action = self.action_global.get_action(JN.Module)

            if action == JN.Top:

                return [self.global_declarations(JN.Top), " * EOF"]

            else:

                return "error"

        elif action == JN.Top:

            action = self.action_global.get_action(JN.Top)

            if action == JN.Pfundef:

                return self.global_declarations(JN.Pfundef)

            if action == JN.Param:

                return self.global_declarations(JN.Param)

            if action == JN.Pglobal:

                return self.global_declarations(JN.Pglobal)

        elif action == JN.Call_conv:

            action = self.action_global.get_action(JN.Call_conv)

            if action == "export":

                return "export"

            else:

                return "inline"  # inline is default

        elif action == JN.Pfundef:

            decl            = self.global_declarations(action=JN.Call_conv)
            function_name   = self.expressions(action=JN.Ident, scope=JS.Function_name, r_depth=0)
            input_param     = self.expressions(action=JN.Var, scope=JS.Decl, r_depth=0)
            input_param_type= self.functions(action=JN.Stor_type, r_depth=0)

            if len(input_param_type) > 3:

                self.variables[JS.Arrays].append(input_param)

            if input_param_type[2] == JT.INT:

                input_param_type[0] = "inline"

            self.variable_types[input_param]            = input_param_type[2]
            self.variables_of_type[input_param_type[2]] = [input_param]
            self.variables_input                        = [input_param]
            self.variables_storage[input_param]         = input_param_type[0]

            result = [decl, " "]
            result += ["fn ", function_name, "("]
            result += input_param_type
            result.append(" ")
            result.append(input_param)
            result.append(")")

            if self.action_functions.get_action(sub="return"):
                return_type = self.functions(action=JN.Stor_type, r_depth=0)

                result.append(" -> ")
                result += return_type
                self.function_return = True
                self.return_types = return_type[1]

            result_1, result_2 = self.functions(action=JN.Pfunbody, r_depth=0)
            result += result_1

            if self.function_return:

                return_var = None

                if len(self.variables_input) > 0 and self.variable_types[self.variables_input[0]] == JT.U64:

                    return_var      = self.get_variable(scope=JT.U64)
                    return_var_type = JT.U64

                    if self.variables_input[0] == return_var:

                        result += ['reg', ' ', JT.U64, ' ', 'out', ';\n']
                        if return_var in self.variables[JS.Arrays]:

                            result_2 = result_2[:-4] + ["out = ", return_var,"[1];\n", result_2[-4]] + result_2[-3:]

                        else:

                            result_2 = result_2[:-4] + ["out = ", return_var,";\n", result_2[-4]] + result_2[-3:]

                        return_var = "out"


                        self.variables_storage[return_var] = "reg"
                        self.variable_types[return_var] = JT.U64

                elif JT.U64 in self.variables_of_type:

                    return_var = self.get_variable(scope=JT.U64)
                    return_var_type = JT.U64

                else:

                    for var in self.variable_types.keys():

                        if self.variable_types[var] != JT.BOOL and self.variable_types[var] != JT.INT:

                            return_var          = self.get_variable(scope=JS.Variables)
                            return_var_type     = self.variable_types[return_var]

                    if return_var is None:

                        return_var = self.get_variable(scope=JS.Variables)
                        return_var_type = self.variable_types[return_var]

                if self.variable_types[return_var] == JT.INT:

                    self.variables_storage[return_var] = "inline"
                    index = result.index(return_var)
                    result[index-4] = "inline"

                return_var_storage  = self.variables_storage[return_var]

                if return_var not in self.variables_assigned:

                    self.variables_used_before_assignment.append(return_var)

                index_append = 0

                if "v0" in self.variables[JS.Arrays]:

                    index_append = 1

                if return_var in self.variables[JS.Arrays] and len(return_type) < 4:

                    result[15 + index_append] = "[5]" + result[15 + index_append]

                if return_var not in self.variables[JS.Arrays]:

                    index_arrow = result.index(" -> ")
                    if result[index_arrow + 4] == "[5]":
                        result[index_arrow + 4] = ""

                result[12 + index_append] = return_var_storage
                result[14 + index_append] = return_var_type
                result_2[-3] = return_var

            if self.variables_input[0] in self.variables_used_before_assignment:

                self.variables_used_before_assignment.remove(self.variables_input[0])

            result_assignments  = []
            bool_assignments    = []

            self.variables_used_before_assignment = list(set(self.variables_used_before_assignment))

            for var in self.variables_used_before_assignment:

                if self.variable_types[var] == JT.BOOL:

                    if self.variable_types[self.variables_input[0]] == JT.BOOL:

                        assignment = [var, " = ", self.variables_input[0], ";\n"]
                        result_assignments += assignment

                    else:

                        bool_assignments.append(var)

            if len(bool_assignments) > 0:

                if self.variable_types[self.variables_input[0]] != JT.U64:

                    self.variable_types[self.variables_input[0]] = JT.U64
                    result[7] = JT.U64

                assignment = [bool_assignments[0]]

                for var in bool_assignments[1:]:

                    assignment += [", ", var]

                for _ in range(5 - len(bool_assignments)):

                    assignment = ["_, "] + assignment

                if self.variables_input[0] in self.variables[JS.Arrays]:

                    assignment += [" = #CMP(", self.variables_input[0], "[1], 42);\n"]

                else:

                    assignment += [" = #CMP(", self.variables_input[0], ", 42);\n"]

                result_assignments += assignment

            for var in self.variables_used_before_assignment:

                if self.variable_types[var] != JT.BOOL and var != "out":                                                #TODO to ensure boolean we added input

                    assignment = [var, " = ", np.random.randint(0, 1000), ";\n"]

                    if var in self.variables[JS.Arrays]:

                        assignment[1] = "[1] = "

                    result_assignments += assignment

            result += result_assignments + result_2

            return result

        elif action == JN.Param:

            return [JN.Param, self.types(action=JN.Ptype), self.expressions(action=JN.Ident, r_depth=0),
                    " = ", self.expressions(action=JN.Pexpr, r_depth=0)]

        elif action == JN.Pglobal:

            var         = self.expressions(action=JN.Ident, r_depth=0)
            var_type    = self.variable_types[var]
            value       = self.expressions(action=JN.Pexpr, scope=var_type, evaluation_type=var_type, r_depth=0)
            result      = [var, "="]

            if isinstance(value, list):
                result += value
            else:
                result.append(value)

            return result

        else:

            raise Exception("GLOBAL DECLARATION NO MATCH")

    """
    
        EXPRESSIONS
        
        Are at a variable level as they can be recursively defined
    
    """

    def expressions(self, action=None, evaluation_type=None, scope=None, r_depth=0):

        r_depth = r_depth + 1

        if action == JN.Pexpr:

            action = self.action_expressions.get_action(sub=JN.Pexpr, scope=scope, r_depth=r_depth)

            """
            
                Terminating actions
            
            """

            if action == "true" or action == "false":

                if scope != JT.BOOL:

                    return self.expressions(action=JN.Pexpr, scope=scope, evaluation_type=evaluation_type)

                elif action == "true":

                    return ["true"]

                elif action == "false":

                    return ["false"]

            if action == "int":

                if evaluation_type == JT.BOOL:

                    return self.expressions(action=JN.Pexpr, scope=scope, evaluation_type=evaluation_type)

                else:

                    return [np.random.randint(0,10000)]

            if action == JN.Var:

                result = self.expressions(action=JN.Var, scope=scope, r_depth=r_depth)

                if result is None:

                    return self.expressions(action=JN.Pexpr, scope=scope, evaluation_type=evaluation_type, r_depth=r_depth)

                else:

                    if result not in self.variables_assigned and result not in self.variables_used_before_assignment:

                        self.variables_used_before_assignment.append(result)

                    if result in self.variables[JS.Arrays]:

                        result = [result, "[1]"]

                    return result

            """
            
                Branching actions
            
            """

            if action == "array":

                """
                
                    If there do not exist a declared array variable then this is a bad call 
                
                """

                var = self.expressions(action=JN.Var, scope=JS.Arrays, evaluation_type=evaluation_type, r_depth=r_depth)

                if var is not None:

                    if isinstance(var, list):                                                                           #TODO fix this

                        result = var

                    else:

                        result = [var, "["]
                        """
                        exp = self.expressions(action=JN.Pexpr, scope=JT.INT, evaluation_type=JT.INT, r_depth=r_depth)
                        if isinstance(exp, list):
                            result += exp
                        else:
                            result.append(exp)
                        """
                        result.append("1")
                        result.append("]")

                    if result[0] not in self.variables_assigned and result[0] not in self.variables_used_before_assignment:

                        self.variables_used_before_assignment.append(result[0])


                    return result

                else:

                    return self.expressions(action=JN.Pexpr, scope=scope, evaluation_type=evaluation_type, r_depth=r_depth)

            if action == "negvar":

                exp = self.expressions(action=JN.Pexpr, scope=scope, evaluation_type=evaluation_type, r_depth=r_depth)
                opera = self.expressions(action=JN.Peop1, scope=scope, evaluation_type=evaluation_type, r_depth=r_depth)
                result = ["("]
                result.append(opera)
                if isinstance(exp, list):
                    result += exp
                else:
                    result.append(exp)
                result.append(")")

                return result

            if action == "exp":

                if evaluation_type == JT.BOOL:

                    new_ev_type = self.action_types.get_action(sub="eval_type")

                else:

                    new_ev_type = evaluation_type

                if new_ev_type != JT.BOOL and evaluation_type == JT.BOOL:                                               #TODO this should be cleaned as standised

                    operator = "compare"

                else:

                    operator = evaluation_type

                exp1 = self.expressions(action=JN.Pexpr, scope=new_ev_type, evaluation_type=new_ev_type, r_depth=r_depth)
                opera = self.expressions(action=JN.Peop2, scope=scope, evaluation_type=operator, r_depth=r_depth)
                exp2 = self.expressions(action=JN.Pexpr, scope=new_ev_type, evaluation_type=new_ev_type, r_depth=r_depth)

                result = ["("]
                if isinstance(exp1, list):
                    result += exp1
                else:
                    if exp1 in self.variables[JS.Arrays]:
                        result += [exp1, "[1]"]
                    else:
                        result.append(exp1)
                result.append(opera)
                if isinstance(exp2, list):
                    result += exp2
                else:
                    if exp2 in self.variables[JS.Arrays]:
                        result += [exp2, "[1]"]
                    else:
                        result.append(exp2)
                result.append(")")

                return result

        if action == JN.Peop1:

            if evaluation_type == JT.BOOL:

                return "!"

            else:

                return "-"

        if action == JN.Peop2:

            if evaluation_type == JT.BOOL:

                return self.action_expressions.get_action(sub="logic")

            if evaluation_type == "compare":

                return self.action_expressions.get_action(sub="compare")

            else:

                return self.action_expressions.get_action(sub="artemtic")

        if action == JN.Var:

            return self.expressions(action=JN.Ident, scope=scope, evaluation_type=evaluation_type, r_depth=r_depth)

        if action == JN.Ident:

            return self.get_variable(scope, evaluation_type=evaluation_type)

        raise Exception("EXPRESSION NO MATCH")

    """

        INSTRUCTIONS

    """

    def instructions(self, action=None, r_depth=0, scope=None):

        if action == JN.Pinstr:

            action = self.action_instructions.get_action(sub=JN.Pinstr, r_depth=r_depth)

            if action == "arrayinit":

                return ["v0 += 1;"]                                                                                     #TODO what is arrayinit?

            if action == "assign":

                var_to_assign = self.instructions(action=JN.Plvalue, r_depth=r_depth, scope=JS.Variables)

                """
                if var_to_assign == "_":

                    ev_type = self.action_types.get_action(sub="assign_type")

                el
                """
                if not isinstance(var_to_assign, list) and self.variable_types[var_to_assign] == JT.BOOL:

                    u64_var = self.expressions(action=JN.Var, scope=JT.U64)

                    if u64_var is not None:

                        if u64_var in self.variables[JS.Arrays]:

                            result = ["_, _, _, _, ", var_to_assign, " = #CMP(", u64_var, "[1], 42);\n"]

                        else:

                            result = ["_, _, _, _, ", var_to_assign, " = #CMP(", u64_var, ", 42);\n"]

                    else:

                        if len(self.variables_input) > 0 and self.variable_types[self.variables_input[0]] == JT.BOOL:

                            result = [var_to_assign, " = ", self.variables_input[0], ";\n"]

                        else:

                            result = ["_, _,", var_to_assign,", _, _ = #CMP(", self.variables_input[0], ", 42);\n"]

                else:

                    if isinstance(var_to_assign, list):

                        ev_type = self.variable_types[var_to_assign[0]]

                    else:

                        ev_type = self.variable_types[var_to_assign]

                    assign_op      = self.instructions(action=JN.Peqop, scope=ev_type)
                    value_to_assign= self.expressions(action=JN.Pexpr, scope=ev_type, evaluation_type=ev_type)

                    if isinstance(var_to_assign, list):

                        result = var_to_assign
                        var_to_assign = var_to_assign[0]

                    else:

                        result = [var_to_assign]

                    if not isinstance(value_to_assign, list):

                        value_to_assign = [value_to_assign]

                    result.append(assign_op)
                    result += value_to_assign
                    result.append(";")

                """
                
                    Append the variable to assigned variables
                
                """

                if var_to_assign not in self.variables_used_before_assignment:

                    self.variables_assigned.append(var_to_assign)

                return result

            if action == "if":

                result = ["if "]
                condition = self.expressions(action=JN.Pexpr, scope=JT.BOOL, evaluation_type=JT.BOOL, r_depth=r_depth)
                if isinstance(condition, list):
                    result += condition
                else:
                    result.append(condition)
                result += self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)

                return result

            if action == "ifelse":

                result = ["if "]
                result += self.expressions(action=JN.Pexpr, scope=JT.BOOL, evaluation_type=JT.BOOL)
                result += self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)
                result.append(" else ")
                result += self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)

                return result

            if action == "forto" or action == "fordown":

                if JT.INT.name.lower() in self.variables_of_type:

                    if action == "forto":

                        """
                            
                            They all need to be the same type
                        
                        """
                        first_var = self.expressions(action=JN.Var, scope=JT.INT)
                        second_var = self.expressions(action=JN.Pexpr, scope=JT.INT, evaluation_type=JT.INT)
                        third_var = np.random.randint(0, 1000) #self.expressions(action=JN.Pexpr, scope=JT.INT, evaluation_type=JT.INT) #To avoid assertion fail

                        return ["for ", first_var, " = ", second_var, " to ", third_var,
                                self.instructions(action=JN.Pblock, r_depth=r_depth)]

                    if action == "fordown":

                        """
        
                            They all need to be the same type
        
                        """
                        first_var = self.expressions(action=JN.Var, scope=JT.INT, evaluation_type=JT.INT)
                        var_type = self.variable_types[first_var]
                        second_var = self.expressions(action=JN.Pexpr, scope=JT.INT, evaluation_type=JT.INT)
                        third_var = self.expressions(action=JN.Pexpr, scope=JT.INT, evaluation_type=JT.INT)

                        return ["for ", first_var, " = ", second_var, " downto ", third_var,
                               self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)]
                else:

                    return self.instructions(action=JN.Pinstr, scope=scope)

            if action == "while":

                start_end = self.action_instructions.get_action(sub="while")
                result = ["while "]
                if start_end:
                    result += self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)

                result += "("
                bool_exp = self.expressions(action=JN.Pexpr, evaluation_type=JT.BOOL, scope=JT.BOOL)
                if isinstance(bool_exp, list):
                    result += bool_exp
                else:
                    result.append(bool_exp)
                result += ")"

                if not start_end:
                    result += self.instructions(action=JN.Pblock, r_depth=r_depth, scope=JS.Variables)

                return result

        if action == JN.Peqop:
            if scope == JT.BOOL:
                return self.action_instructions.get_action(sub="logic")
            else:
                return self.action_instructions.get_action(sub=JN.Peqop)                                                #TODO make such that it return <var><peqop><var>

        if action == JN.Pblock:

            result = ["{\n"]
            for _ in range(self.action_instructions.get_amount_of_instructions()):

                result += self.instructions(action=JN.Pinstr, scope=JS.Variables, r_depth=r_depth)

            result += ["\n}"]                                                                                           #TODO should be able to do multiple

            return result

        if action == JN.Plvalue:

            action = self.action_instructions.get_action(sub=JN.Plvalue, r_depth=r_depth)

            if action == "_":

                return "_"

            if action == JN.Var:

                result =  self.expressions(action=JN.Var, r_depth=r_depth, scope=scope)

                if result in self.variables[JS.Arrays]:

                    return [result, "[1]"]

                else:

                    return result

            if action == "array":

                var = self.expressions(action=JN.Var, r_depth=r_depth, scope=JS.Arrays)

                if var is not None:

                    index = 1  #self.expressions(action=JN.Pexpr, r_depth=r_depth, scope=JT.INT, evaluation_type=JT.INT)
                    result = [var, "["]
                    result += index
                    result.append("]")

                    return result

                else:

                    return self.instructions(action=JN.Plvalue, r_depth = r_depth, scope=scope)

        raise Exception("INSTRUCTION NO MATCH")

    """
    
        FUNCTIONS
    
    """

    def functions(self, action=None, r_depth=0):

        r_depth = r_depth + 1

        if action == JN.Pfunbody:

            result_1          = ["{\n"]
            amount_of_vars  = range(self.action_functions.get_amount_of_decls())
            amount_of_incs  = range(self.action_functions.get_amount_of_instructions())

            for _ in amount_of_vars:

                result_1 += self.functions(action=JN.Pvardecl, r_depth=r_depth)

            result_2 = []
            for _ in amount_of_incs:

                result_2 += self.instructions(JN.Pinstr, r_depth=r_depth, scope=JS.Variables)
                result_2 += "\n"

            if self.function_return:

                result_2 += ["return ", None, ";"]

            result_2 += ["\n}"]

            return result_1, result_2

        if action == JN.Storage:

            return self.action_functions.get_action(sub=JN.Storage, r_depth=r_depth)

        if action == JN.Stor_type:

            result = [self.functions(action=JN.Storage, r_depth=r_depth)," "]
            var_type = self.types(action=JN.Ptype)

            if isinstance(var_type, list):
                result += var_type
            else:
                result.append(var_type)

            return result

        if action == JN.Pvardecl:

            stor_type   = self.functions(action=JN.Stor_type, r_depth=r_depth)
            variable    = self.expressions(action=JN.Var, scope=JS.Decl, r_depth=r_depth)
            var_type    = stor_type[2]
            storage     = stor_type[0]

            if var_type == JT.INT:
                storage = "inline"
                stor_type[0] = "inline"


            """
            
                If var_type is of the form <type><brackets> it should be added to arrays as well
            
            """

            self.variables_storage[variable]    = storage
            self.variable_types[variable]       = var_type

            if len(stor_type) > 3:

                self.variables[JS.Arrays].append(variable)

            if var_type in self.variables_of_type:

                self.variables_of_type[var_type].append(variable)

            else:

                self.variables_of_type[var_type] = [variable]

            result =    stor_type
            result +=   [" ", variable, ";\n"]

            return result

        raise Exception("FUNCTION NO MATCH")

    """
    
        TYPES
    
    """

    def types(self, action=None, r_depth=0):

        r_depth = r_depth + 1

        if action == JN.Ptype:

            action = self.action_types.get_action(sub=JN.Ptype)

            if action == JT.BOOL:

                return JT.BOOL

            if action == JT.INT:

                return JT.INT

            if action == JN.Utype:

                return self.types(action=JN.Utype)

            if action == "array":

                return [self.types(action=JN.Utype), "[5]"]                                                             #TODO should be somekind of int declearing the size

        if action == JN.Utype:

            return self.action_types.get_action(sub=JN.Utype, r_depth=r_depth)

        raise Exception("TYPE NO MATCH")