def main () -> int
  let s str "hello"
  let t str "world"
  let u str (+ s "-")
  set u (+ u t)
  (call print u)
  (call print (call substring u 0 5))
  (call print (call list_length u))
  (call print (call string-append s " " t))
  return 0
end
