"""Finite phase-grid generation and a conservative equivalence quotient."""
from __future__ import annotations
from dataclasses import dataclass

ACTIONS=('noise','load','hydrate','noise','commit','transition','noise')
HORIZONS={'H':3,'C':5,'T':7}
@dataclass(frozen=True)
class Schedule:
    horizon:str
    gap:int
    def as_dict(self):return {'horizon':self.horizon,'gap':self.gap}

def grid():return [Schedule(h,g) for h,n in HORIZONS.items() for g in range(n+1)]
def phase_class(s):
    # A gap is after exactly gap prefix actions. Keep H, C, and T distinct.
    return (s.horizon, sum(a in ('hydrate','commit','transition') for a in ACTIONS[:s.gap]))
def quotient():
    representatives={}
    for s in grid():representatives.setdefault(phase_class(s),s)
    return list(representatives.values())
def ordered(schedules,hint=None):
    # Hints only affect order. The full set of representatives is retained.
    ranks={'state-binding':['C','H','T'],'keyed':['T','C','H'],'native':['H','C','T']}
    hs=ranks.get(hint,['H','C','T'])
    return sorted(schedules,key=lambda s:(hs.index(s.horizon),s.gap))
