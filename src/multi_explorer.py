"""Two-edit phase language and conservative within-gap swap quotient."""
from dataclasses import dataclass
@dataclass(frozen=True)
class PairSchedule:
 horizon:int
 a:int
 b:int
 order:str
 def as_dict(self):return dict(horizon=self.horizon,a=self.a,b=self.b,order=self.order)
def pair_grid():
 return [PairSchedule(h,a,b,o) for h in [1,2,3] for a in range(h+1) for b in range(h+1) for o in (['ab','ba'] if a==b else ['ab' if a<b else 'ba'])]
def independent(effects,ha,hb):
 a,b=effects[ha],effects[hb]
 if not a['known'] or not b['known']:return False
 ar,aw,br,bw=map(set,[a['reads'],a['writes'],b['reads'],b['writes']])
 return not(aw&(br|bw) or bw&(ar|aw))
def representative(s,commutes):
 return PairSchedule(s.horizon,s.a,s.b,'ab') if commutes and s.a==s.b else s
def pair_quotient(commutes):return list(dict.fromkeys(representative(s,commutes) for s in pair_grid()))
