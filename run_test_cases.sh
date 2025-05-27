#!/bin/bash

cd "$(dirname "$0")"

TEST_CASES_FILE="test/test_cases.txt"

if [ ! -f "$TEST_CASES_FILE" ]; then
  echo "未找到 $TEST_CASES_FILE 文件"
  exit 1
fi

while IFS= read -r testcase || [ -n "$testcase" ]; do
  if [ -n "$testcase" ] && [[ "$testcase" != \#* ]]; then
    echo "\n===== 正在执行: $testcase ====="
    python3 -m pytest "$testcase"
  fi
done < "$TEST_CASES_FILE"