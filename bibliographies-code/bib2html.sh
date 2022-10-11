#!/usr/bin/env bash

VENV_NAME=ir-anthology-env
PYTHON=${VENV_NAME}/bin/python3
INPUT_PATH=../bibliographies-webis/
OUTPUT_PATH=../bibliographies-webis/html/

{
  if [ ! -d "${VENV_NAME}" ];then
    echo "Setting up ${VENV_NAME} (this is done only once)"
    python3 -m venv ${VENV_NAME}
    chmod +x ${VENV_NAME}/bin/activate
    /bin/sh ${VENV_NAME}/bin/activate
    ${PYTHON} -m pip install -r requirements.txt
  fi
} || { # catch
  rm -rf ${VENV_NAME}
  exit 1
}

rm -rf ${OUTPUT_PATH}
${PYTHON} bib2html.py --input-path ${INPUT_PATH} --output-path ${OUTPUT_PATH} -cf

