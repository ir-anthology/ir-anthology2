#!/usr/bin/env bash

if [ "$1" == "-h" -o "$1" == "--help" -o $# -gt 1 ];then
  echo "Usage: $0 [<bibliographies-directory>]"
  exit 1
fi

# Options
source_dir=$(dirname $0)
bib_dir=$source_dir/../bibliographies-webis
if [ $# -eq 1 ];then
  bib_dir=$1
fi

# Constants
months="jan feb mar apr may jun jul aug sep oct nov dec"

function bibtool_sort_order() {
  local input="$1"
  grep -P '^\s*[\w-][\w-]*\s*=' "${input}" \
    | sed 's/^\s*\([\w-][\w-]*\).*/\1/' \
    | sort \
    | uniq \
    | awk '{if (NR != 1) {printf " # "}; printf "%s", $1}'
}

# Formatting functions
function bib_format_part_generic() {
  local sort_key="$1"
  shift

  local input
  for input in $@;do
    echo "Formatting part: $(head -n 1 $input)"
    # Not formatting the first line
    head -n 1 $input > "$input--head.bib"
    echo "" >> "$input--head.bib"
    tail -n +2 "$input" > "$input--headless.bib"
    mv "$input--head.bib" $input
    $source_dir/bibtool \
        -@ \
        -s -- "sort.format = {$sort_key}" \
        -- 'print.align = 26' \
        -- 'print.align.key = 0' \
        -- 'print.equal.right = off' \
        -- 'pass.comments = on' \
        -- 'print.line.length = 10000' \
        -- 'print.use.tab = off' \
        -- "sort.order = { * = $(bibtool_sort_order $input--headless.bib) }" \
        -- 'rewrite.rule = {doi# "https?://.*doi.*\.org/\(10\.[0-9]+/.+\)"# "\1"}' \
        "$input--headless.bib" \
      | sed '/./,$!d' \
      >> "$input"
    echo "" >> $input
    echo "" >> $input
    echo "" >> $input
    rm "$input--headless.bib"
  done
}

function bib_format_part_by_key() {
  local input
  for input in $@;do
    bib_format_part_generic "%w($key)" "$input"
  done
}

function bib_format_part_publications() {
  local input
  for input in $@;do
    # Substituting each month by a two-digit number
    local m=1
    for month in $months;do
      local number=$(printf "%02d" "$m")
      sed -i "s/\(^ *month = *\)[{]*$month[}]*, *$/\1$number,/" "$input"
      let m++
    done

    # Defining the sort order.
    # - By key, then firstyear (only to identify it as collection)
    # - If that fails (no firstyear => no collection), by year, then month (2-digit), then booktitle (99 words), then key (2 words, name + year with suffix)
    # - If that fails, then the same but use 13 for the month (in case no month was given)
    # - If that fails, then repeat the last two but use zzzzz for the booktitle (in case no booktitle is given)
    local sort_key='%w($key) %d(firstyear) # %d(year) %2d(month) %99w(booktitle) %2w($key) # %d(year) %2d(month) zzzzz %2w($key) # %d(year) 13 %99w(booktitle) %2w($key) # %d(year) 13 zzzzz %2w($key)'

    bib_format_part_generic "$sort_key" "$input"

    # Substituting back the months
    m=1
    for month in $months;do
      local number=$(printf "%02d" "$m")
      sed -i "s/\(^ *month = *\)$number, *$/\1$month,/" "$input"
      let m++
    done
  done
}

# Actual execution
function bib_format_generic() {
  local bib_format_part_function="$1"
  local input=$2

  echo "---------------------------------------------------"
  echo "Formatting: $input with $bib_format_part_function"
  csplit -z -f "$bib_dir/$input--" -b "%03d.bib" "$bib_dir/$input" '/^%%% /' '{*}' > /dev/zero
  bib_parts=$(ls $bib_dir/$input--* | sort)
  $bib_format_part_function $bib_parts
  cat $bib_parts > $bib_dir/$input
  rm $bib_parts
}

for input in $(ls $bib_dir | grep ".bib$");do
  case "$input" in
    webis-people.bib)
      bib_format_generic bib_format_part_by_key $input
      ;;
    webis-publications.bib)
      bib_format_generic bib_format_part_publications $input
      ;;
    webis-theses.bib)
      bib_format_generic bib_format_part_publications $input
      ;;
  esac
done
