import unittest
from programs import interpret
class Tests(unittest.TestCase):
 def test_patch(self):self.assertEqual(interpret('E[0][1]=3\nE[1][1]=1',[3,1,1,1,3,3]),[3,3,1,1,1,3])
 def test_reset_then_patch(self):self.assertEqual(interpret('```python\nE=[[3,1,1],[1,3,3]]\nE[0][1]=3\nE[1][1]=1\n```',[0]*6),[3,3,1,1,1,3])
 def test_reject(self):
  for s in ['import os','E[0][0]=open("x")','E=[[1]*3]*2','E[-1][0]=2','E[0][0]=True','E[0][0]=9','while True: pass','E[0][0]=2\nprint(1)']:
   with self.assertRaises((ValueError,SyntaxError)):interpret(s,[2]*6)
if __name__=='__main__':unittest.main()
