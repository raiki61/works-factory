"""TDD の筋書きの実行器（docs/design/fix.md の 14.1）: 第 1 引数の書き先に 1 件が failure の JUnit XML を書いて 1 で終わる。
後ろの引数の名指しは読まない"""
import sys

with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write('<testsuite tests="1" failures="1"><testcase classname="test_stats" name="test_mean">'
            '<failure message="ZeroDivisionError">ZeroDivisionError</failure></testcase></testsuite>\n')
sys.exit(1)
