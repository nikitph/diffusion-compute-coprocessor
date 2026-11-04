"""Mechanism invariants independent of model quality; no GPU needed."""
import unittest
from run import diffuse,digest

class Tokenizer:
    mask_token_id=99
    def decode(self,x):return str(x)
class FakeBackend:
    tok=Tokenizer();tokens=[10,11,12,13,14];calls=0
    def predict(self,ids,slots):
        self.calls+=1
        return [3,3,1,1,1,3],[.9,.8,.7,.6,.5,.4]
class CanvasTests(unittest.TestCase):
    def test_arrival_and_repair(self):
        b=FakeBackend();slots=[1,3,5,7,9,11];ids=[77,99]*6+[88];events=[]
        candidate=diffuse(b,ids,slots,3,events)
        self.assertEqual(candidate,[3,3,1,1,1,3]);self.assertEqual(ids.count(99),3)
        locked=ids[:];report=[81,82,83];ids+=report
        for p in slots:ids[p]=99
        diffuse(b,ids,slots,6,events)
        self.assertEqual(ids[-3:],report)
        self.assertTrue(all(ids[i]==v for i,v in enumerate(locked) if i not in slots))
        self.assertEqual([b.tokens.index(ids[p]) for p in slots],candidate)
        self.assertEqual(ids.count(99),0)
if __name__=='__main__':unittest.main()
