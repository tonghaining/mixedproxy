#!/usr/bin/env python3

import os
import lark
# from dat3m_litmus import *
from litmus import *
from constants import *


################################################################################
# Dat3m litmus test parser
################################################################################


file_path = os.path.dirname(os.path.realpath(__file__))
grammar_path = os.path.join(file_path, "dat3m_grammar.lark")
with open(grammar_path, "r") as f:
    grammar = f.read()

class ParseException(Exception):
    def __init__(self, text, meta, message):
        text = text[meta.start_pos : meta.end_pos]
        text = " ".join([i.strip() for i in text.split("\n")])
        self.message = f"Line {meta.line}: '{text}': {message}"

    def __str__(self):
        return self.message


@lark.v_args(inline=True, meta=True)
class Dat3mTransformer(lark.Transformer):
    def __init__(self, text, model):
        self.text = text
        self.instruction_count = 0
        self.model = model
        self.thread_navigator = {}
        self.events = {}
        self.reg_pred = {}

    def _new_id(self):
        c = self.instruction_count
        self.instruction_count += 1
        return f"i{c}"

    def register_decl(self, meta, thread_id, register, constant):
        self.reg_pred[register] = constant
        pass

    def location_decl(self, meta, location, constant):
        return Address(name=location, space=GLOBAL)

    def _get_event(self):
        result = []
        for thread_info in self.events:
            tid = ThreadID(*thread_info)
            result.append(Thread(tid, self.events[thread_info]))
        return result

    def start(self, meta, header, variable_decl_list, instructions, assertion_list):
        return LitmusTest(
            model=self.model,
            addresses=[i for i in variable_decl_list.children if i],
            threads=self._get_event(),
            commands=assertion_list.children,
        )

    def header(self, *args):
        return None

    def thread_decl(self, meta, thread_id, cta_id, gpu_id):
        self.thread_navigator[meta.column] = (int(gpu_id), int(cta_id), int(thread_id))

    def _check_sem_scope(self, meta, sem, scope, event):
        if sem == WEAK:
            if scope:
                raise ParseException(
                    self.text,
                    meta,
                    f"illegal encoding: .{sem} accesses should not have scope",
                )
            return RELAXED, SYS
        if event == STORE and sem not in [WEAK, RELAXED, RELEASE]:
            raise ParseException(
                self.text,
                meta,
                f"illegal encoding: store does not support .{sem} accesses",
            )
        if event == LOAD and sem not in [WEAK, RELAXED, ACQUIRE]:
            raise ParseException(
                self.text,
                meta,
                f"illegal encoding: load does not support .{sem} accesses",
            )
        if event == FENCE and sem not in [ACQ_REL, BAR_SYNC]:
            raise ParseException(
                self.text,
                meta,
                f"illegal encoding: fence does not support .{sem} accesses",
            )
        if event == FENCE and sem == BAR_SYNC:
            sem = SC
        return sem, scope

    def _update_thread_event(self, meta, event):
        if meta.column not in self.thread_navigator:
            raise ParseException(
                self.text,
                meta,
                f"Not aligned: {meta.column} starting point not match all threads",
            )
        thread_info = self.thread_navigator[meta.column]
        if thread_info not in self.events:
            self.events[thread_info] = [event]
        else:
            self.events[thread_info].append(event)

    def load(self, meta, op, sem, scope, dst, src):
        sem, scope = self._check_sem_scope(meta, sem, scope, LOAD)
        event = Load(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            proxy=GENERIC,
            dst=dst,
            src=src,
            return_value=NoValue(),
            line=meta.line,
        )
        self._update_thread_event(meta, event)

    def store(self, meta, op, sem, scope, dst, value):
        sem, scope = self._check_sem_scope(meta, sem, scope, STORE)
        event = Store(
            name=self._new_id(),
            op=op,
            sem=sem,
            scope=scope,
            proxy=GENERIC,
            dst=dst,
            value=value,
            line=meta.line,
        )
        self._update_thread_event(meta, event)

    def fence(self, meta, op, sem, scope):
        sem, scope = self._check_sem_scope(meta, sem, scope, FENCE)
        event = Fence(
            name=self._new_id(),
            sem=sem,
            scope=scope,
            line=meta.line,
        )
        self._update_thread_event(meta, event)

    def sem(self, meta, dot=None, arg=None):
        if arg:
            return str(arg)
        else:
            return None

    def scope(self, meta, dot=None, arg=None):
        if arg:
            return str(arg)
        else:
            return None

    def weak(self, meta, *args):
        return None

    def none(self, meta):
        return None

    def register(self, meta, reg):
        return NamedValue(str(reg))

    def constant(self, meta, n):
        return Integer(int(n))

    def eq(self, meta, left, right):
        return Equal(left, right)

    def neq(self, meta, left, right):
        return Not(Equal(left, right))

    def and_(self, meta, left, right):
        return And(left, right)

    def or_(self, meta, left, right):
        return Or(left, right)

    def not_(self, meta, expr):
        return Not(expr)

    def condition(self, meta, cmd):
        return cmd

    def num(self, meta, n):
        return int(n)

    def num_value(self, meta, n):
        return Integer(n)

    def no_name(self, meta):
        return ""

    def exist_(self, meta, expr):
        name = f"exist{self._new_id()}"
        return Command(name, expr, expected=True, line=meta.line)

    def forbid_(self, meta, expr):
        name = f"forbid{self._new_id()}"
        return Command(name, Not(expr), expected=False, line=meta.line)

    def forall_(self, meta, expr):
        name = f"forall{self._new_id()}"
        return Command(name, expr, expected=False, line=meta.line)

    def assertion_register(self, meta, thread_id, register):
        return register


_parser = lark.Lark(grammar, propagate_positions=True)


def parse(model, contents):
    return Dat3mTransformer(contents, model).transform(_parser.parse(contents))


if __name__ == "__main__":
    import sys

    test = parse(sys.stdin.read())
    print(test)

    expanded = test.expand_operations()
    print(expanded)

    alloy = expanded.to_alloy()
    print(alloy)
