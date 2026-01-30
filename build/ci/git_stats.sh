#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Collection of commands to extract some statistics form Git

# git shortlog  --since 2021-01-01 -sn branch_v3_11 | less
echo "Top 10 contributors to the current branch using number of commits"
git shortlog  --since 2021-01-01 -sn branch_v3_11 | head -n 10

echo

START_DATE=2021
BRANCH=${GIT_BRANCH:-master}
echo "Detailed stats for main team members since $START_DATE, branch $BRANCH (GIT_BRANCH)"
echo "Name: commits, added lines, removed lines, total lines"
for i in "Marco Mambelli" "Bruno Coimbra" "Namratha Urs" "Marco Mascheroni" "Dennis D. Box"; do
    echo -n "$i: "
    git log --since=$START_DATE  --author="$i" --pretty=tformat: --numstat $BRANCH | awk '{ comm += 1; add += $1; subs += $2; loc += $1 - $2 } END { printf "%s, %s, %s, %s\n", comm, add, subs, loc }'
done
