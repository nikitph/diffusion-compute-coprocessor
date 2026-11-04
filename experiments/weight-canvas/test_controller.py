import unittest
from controller import *

class Tests(unittest.TestCase):
    def test_reference(self):
        r=evaluate(REFERENCE,scenarios(810,10000));self.assertEqual(r['caught'],10000)
    def test_independent_policy(self):
        for obs in scenarios(91,1000):
            d=obs[0]+obs[1]-obs[2]
            expected=-1 if d<-.1 else 1 if d>.1 else 0
            self.assertEqual(action(REFERENCE,obs)[0],expected)
    def test_faults(self):
        for e in FAULTS.values():self.assertLess(evaluate(e,scenarios(12,512))['caught'],512)
    def test_schema(self):
        for e in [[1]*5,[1]*7,[True]*6,[5]*6,[float('nan')]*6]:
            with self.assertRaises(ValueError):validate(e)
    def test_feedback_version(self):
        e=FAULTS['velocity_reversed'];rows=scenarios(51,64)
        self.assertEqual(feedback(e,rows)['candidate'],version(e))
        self.assertNotEqual(feedback(e,rows)['examples'],feedback(e,rows,True)['examples'])
    def test_splits(self):
        a=set(map(tuple,scenarios(20261104,64)))
        b=set(map(tuple,scenarios(20261105,512)))
        self.assertFalse(a&b)

if __name__=='__main__':unittest.main()
