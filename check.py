import os, os.path
import re
import json
import multiprocessing as mp

from tqdm import tqdm
import numpy as np
import click

from transform import parse_header_line

COMPONENT_INDICES = [
  "date",
  "tm",
  "tx",
  "tn",
  "pr",
  "sr",
  "sd",
]

def parse_data_line(line):
  # 年(2 バイト)，月(2 バイト)，気象値(3 バイト×月日数)
  year = int(line[:2])
  month = int(line[2:4])
  data = line[4:]

  data_len = len(data)
  d = np.empty(int(data_len / 3), dtype=np.int16)
  for (i, j) in enumerate(range(0, data_len, 3)):
    x = data[ j : j+3 ]
    if x == '   ':
      d[i] = -1 # hopefully this doesn't happen!
    else:
      d[i] = x

  return (year, month, d)


def compare_data(outroot, mesh, component, area, data):
  (year, month, d) = data
  mesh_1 = mesh[:4]
  mesh_2 = mesh[:6]
  jsonfile = os.path.join(outroot, mesh_1, mesh_2, mesh + ".json")
  # print(mesh, jsonfile)
  with open(jsonfile, "r") as f:
    parsed_json = json.load(f)

  idx = COMPONENT_INDICES.index(component)

  if component in ["tm", "tx", "tn"]:
    d = np.where(d > 500, d - 1000, d)

  if component in ["tm", "tx", "tn", "sr", "sd"]:
    d = d / 10

  differences = []

  for (day, daydata) in enumerate(d, start=1):
    mdstr = f"{month:02}-{day:02}"
    dayrows = [ x for x in parsed_json if x[0] == mdstr ]
    if len(dayrows) == 0:
      raise RuntimeError("row of data not found for {mesh} {mdstr}")
    dayrow = dayrows[0]
    processed_val = dayrow[idx]

    same = processed_val == daydata
    # print(f"{mesh} {mdstr} {processed_val} <-> {daydata} ({same})")
    if same == False:
      differences += ((area, mesh, mdstr, component, processed_val, daydata,),) # f"{mesh} {mdstr} in json: {processed_val} != in raw: {daydata}",)
      # raise RuntimeError(f"stop: {mesh} {mdstr} in json: {processed_val} != in raw: {daydata}")

  return differences

def read_file(outroot, component, area, data):
  current_mesh3 = None

  differences = []

  for line in data:
    line = line.rstrip()
    if not (48 <= line[0] and line[0] <= 57):
      # 数字で始まらない行を無視する
      continue

    try:
      if len(line) == 32:
        # ヘッダー
        (mesh3,) = parse_header_line(line)
        current_mesh3 = mesh3

      else:
        # one line has a month of data
        data = parse_data_line(line)
        differences += compare_data(outroot, current_mesh3, component, area, data)

    except ValueError as e:
      print(f"Error in line: {line}")
      raise e

  return differences

def process_input_file(dest, input):
  filename = os.path.basename(input)
  filename_parts = re.match(r"^ms([a-z]{2})([0-9a-z]{2})([0-9]{2})\.dat$", filename, re.I)
  component = filename_parts[1].lower()
  area = filename_parts[2].lower()
  with open(input, "rb") as data:
    diffs = read_file(dest, component, area, data)

  return diffs

def _process(x):
  (dest, input) = x
  return process_input_file(dest, input)

@click.command()
@click.argument("src")
@click.argument("dest")
def main(src, dest="out"):
  """SRC に解凍された1年分のディレクトリーを指定してください。

  DEST に transform.py で処理された（3次メッシュに分けられた）ファイルが入ってるディレクトリーを指定してくだい。
  デフォルトは `out` です。
  """

  items = []
  for root, _dirs, files in os.walk(src):
    for file in files:
      if not file.lower().endswith(".dat"):
        continue
      items.append(os.path.join(root, file))

  processes = int(os.cpu_count() * 0.75)
  if os.cpu_count() == 2:
    processes = 2
  print(f"Using {processes} processes...", flush=True)

  with mp.Pool(processes=processes) as pool, open(os.path.join(".", "check_differences.csv"), "w", encoding="utf-8") as logf:
    logf.write(f"area,mesh,monthdate,component,json_val,raw_val\n")
    iterator = ( (dest, item) for item in items )
    for differences in tqdm(pool.imap_unordered(_process, iterator), total=len(items)):
      for (area, mesh, mdstr, component, processed_val, daydata,) in differences:
        logf.write(f"{area},{mesh},{mdstr},{component},{processed_val},{daydata}\n")

if __name__ == "__main__":
  main()
