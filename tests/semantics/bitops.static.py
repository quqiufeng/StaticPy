# bitops — 位运算兜底（bitand/bitor/bitxor/lshift/rshift/Invert）与 CPython 对齐。
# 来历：位运算曾在 staticpy/static_prelude.scm（生成物）里手改，而真源
# tools/seed/prelude.scm 没动 → split_plugins.py --check 长期红，且重新生成会
# 静默丢掉位运算（构建仍绿，因为构建读的是生成物）。本用例把它钉死在语义差分里。
def main():
  a: int = 12
  b: int = 10
  print(a & b)
  print(a | b)
  print(a ^ b)
  print(a << 3)
  print(a >> 2)
  print(~a)
  print(-8 >> 1)
  print(-1 & 255)
  big: int = 1 << 70
  print(big >> 68)
  print(big & 255)
  m: int = 0
  m = m | (1 << 5)
  m = m | (1 << 9)
  print(m)
  print(m ^ (1 << 9))
  return 0
