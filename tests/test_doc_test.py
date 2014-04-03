import unittest
import doctest
import sys
sys.path.append('..')
import find_link

def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(find_link))
    return tests
