# 3GW transfer-weight fit — temporal instability

Chips are OFF. The test uses the recovered rolling Phase5Q archive only as a
strategy proxy; it is not a vFinal full-season result.

Hand-picked candidates:
- (1.00,0.90,0.75): 2070 total
- (1.00,0.85,0.70): 2093 total
- (1.00,0.80,0.60): 2109 total
- (1.00,0.75,0.50): 2049 total
- (1.00,0.70,0.40): 1886 total

A one-parameter exponential family was then fit:
  w=(1,r,r^2), r in {0.55,...,0.95}.

Selection used GW1-21 only. The fitted development optimum was:
- r=0.75 -> (1.00,0.75,0.5625)
- GW1-21 points 1186
- GW22-38 later check 927
- full-season total 2113
- 55 transfers / 76 hit points

However the fit is not temporally stable. Later GW22-38 strongly preferred
milder decay:
- r=0.90 -> 990 later-period points
- r=0.95 -> 1011 later-period points
versus only 927 for the development-selected r=0.75.

The full-season numerical maximum is r=0.95 with 2118 points, but selecting it
from the same season would be retrospective overfit. Therefore do not freeze
r=0.75 or r=0.95 as a universal optimum.

Interpretation:
- very strong discounting is clearly bad;
- the broad useful region is roughly GW+1 weight 0.75-0.95;
- exact optimum is unstable by period;
- retain a conservative predeclared comparator such as (1.00,0.85,0.70) and
  report sensitivity to nearby decay choices in the eventual vFinal replay;
- if choosing a fitted family, fit r on an independent prior season or multiple
  rolling seasons rather than optimizing on this single season.
