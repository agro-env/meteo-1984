import os, os.path
import re
from datetime import timedelta, date

import multiprocessing as mp
from tqdm import tqdm

import numpy as np

import click

def normalize_year(year):
  # 2078になるまではこの対処で大丈夫かと思います。
  if year >= 78 and year <= 99:
    year += 1900
  else:
    year += 2000
  return year

def parse_data_line(line):
  # 年(2 バイト)，月(2 バイト)，気象値(3 バイト×月日数)
  # year = int(line[:2])
  # month = int(line[2:4])
  data = line[4:]

  data_len = len(data)
  d = np.empty(int(data_len / 3), dtype=np.int16)
  for (i, j) in enumerate(range(0, data_len, 3)):
    x = data[ j : j+3 ]
    if x == '   ':
      d[i] = -1 # hopefully this doesn't happen!
    else:
      d[i] = x

  return d

def parse_header_line(line):
  # 三次メッシュコード(8 バイト)，メッシュ標高(4 バイト)，陸域面積(4 バイト)，水田面積(4 バイト)，畑地面積(4 バイト)，果樹園面積(4 バイト)，森林面積(4 バイト)
  return (
    line[:8].strip().decode(),    # 三次メッシュコード
    # int(line[8:12].strip()),  # メッシュ標高
    # int(line[12:16].strip()), # 陸域面積
    # int(line[16:20].strip()), # 水田面積
    # int(line[20:24].strip()), # 畑地面積
    # int(line[24:28].strip()), # 果樹園面積
    # int(line[28:32].strip()), # 森林面積
  )

def read_file(data):
  current_mesh3 = None
  buffer = []
  out = []

  def flush_buffer():
    nonlocal out
    out += ((current_mesh3, np.concatenate(buffer),),)
    return []

  for line in data:
    line = line.rstrip()
    if not (48 <= line[0] and line[0] <= 57):
      # 数字で始まらない行を無視する
      continue

    try:
      if len(line) == 32:
        # ヘッダー
        (mesh3,) = parse_header_line(line)
        if current_mesh3 is not None:
          buffer = flush_buffer()
        current_mesh3 = mesh3

      else:
        # one line has a month of data
        buffer += ( parse_data_line(line), )

    except ValueError as e:
      print(f"Error in line: {line}")
      raise e

  if current_mesh3 is not None:
    buffer = flush_buffer()

  return out

def _process_archive_item(input):
  filename = os.path.basename(input)
  filename_parts = re.match(r"^ms([a-z]{2})([0-9a-z]{2})([0-9]{2})\.dat$", filename, re.I)
  component = filename_parts[1].lower()
  with open(input, "rb") as data:
    parsed = read_file(data)

  meshes = {}
  for mdata in parsed:
    (meshcode, days) = mdata

    if component in ["tm", "tx", "tn"]:
      days = np.where(days > 500, days - 1000, days)

    meshes[meshcode] = days

  return (component, meshes,)

def _process_all_files(files):
  return dict(map(_process_archive_item, files))

def _merge_components(cmd, meshcode, dummy):
  merged = np.array([
    cmd["tm"].get(meshcode, dummy) / 10,
    cmd["tx"].get(meshcode, dummy) / 10,
    cmd["tn"].get(meshcode, dummy) / 10,
    cmd["pr"].get(meshcode, dummy),
    cmd["sr"].get(meshcode, dummy) / 10,
    cmd["sd"].get(meshcode, dummy) / 10,
  ])
  return merged.transpose()

def _generate_daydata(daydata, date_array):
  out = "["
  for i, d in enumerate(daydata):
    if i != 0:
      out += ","
    out += f"[\"{date_array[i]}\",{d[0]},{d[1]},{d[2]},{int(d[3])},{d[4]},{d[5]}]"
  return out + "]"

def _write_daydata(meshoutdir, mesh, daydata, date_array):
  out = _generate_daydata(daydata, date_array)
  try:
    with open(os.path.join(meshoutdir, mesh + ".json"), "x", encoding='ASCII', buffering=32768) as outf:
      outf.write(out)
    return True
  except FileExistsError:
    return False

def _process_ken_code_files(input):
  (ken_code, files) = input

  existing_files = []

  first_file = os.path.basename(files[0])
  filename_parts = re.match(r"^ms([a-z]{2})([0-9a-z]{2})([0-9]{2})\.dat$", first_file, re.I)
  year = normalize_year(int(filename_parts[3]))

  start_date = date(year, 1, 1)
  end_date = date(year + 1, 1, 1) - timedelta(days=1)
  date_array = [ (start_date + timedelta(n)).strftime("%m-%d") for n in range(int((end_date - start_date).days) + 1) ]
  days_in_this_year = len(date_array)

  component_mesh_data = _process_all_files(files)
  meshcodes = component_mesh_data["tm"].keys()

  dummy = np.full((days_in_this_year), -1)

  for mesh in meshcodes:
    mesh_1 = mesh[:4]
    mesh_2 = mesh[:6]
    meshoutdir = os.path.join(os.path.join(".", "out"), mesh_1, mesh_2)
    os.makedirs(meshoutdir, exist_ok=True)

    daydata = _merge_components(component_mesh_data, mesh, dummy)
    res = _write_daydata(meshoutdir, mesh, daydata, date_array)
    if res is False:
      existing_files += (mesh,)

  return (ken_code, existing_files,)

@click.command()
@click.option("-k", "--only-ken-code", default=None)
@click.option("-p", "--processes", default=int(os.cpu_count() * 0.75))
@click.argument("src")
def main(src, only_ken_code, processes):
  """SRC に解凍された1年分のディレクトリーを指定してください。
  """

  items = []
  for root, _dirs, files in os.walk(src):
    for file in files:
      if not file.lower().endswith(".dat"):
        continue
      items.append(os.path.join(root, file))

  grouped_by_ken = {}
  for item in items:
    filename = os.path.basename(item)
    filename_parts = re.match(r"^ms([a-z]{2})([0-9a-z]{2})([0-9]{2})\.dat$", filename, re.I)
    ken_code = filename_parts[2].upper()
    l = grouped_by_ken.get(ken_code, [])
    l.append(item)
    grouped_by_ken[ken_code] = l

  if only_ken_code is not None:
    allowed_kens = only_ken_code.split(",")
    grouped_by_ken = dict([ (x, grouped_by_ken.pop(x, None)) for x in allowed_kens ])

  os.makedirs(os.path.join(".", "out"), exist_ok=True)

  ken_keys = sorted(grouped_by_ken.keys())
  ken_items = [ (x, grouped_by_ken[x]) for x in ken_keys ]

  # Lock processes to 2 when running in GitHub Actions
  if os.getenv("CI") == "true" and os.cpu_count() == 2:
    processes = 2
  print(f"Using {processes} processes...", flush=True)

  with open(os.path.join(".", "overwritten.log"), "w", encoding="utf-8") as f, mp.Pool(processes=processes) as pool:
    process_method = pool.imap_unordered
    if processes == 1:
      process_method = map
    for (kc, existing_files,) in tqdm(process_method(_process_ken_code_files, ken_items), total=len(grouped_by_ken)):
      tqdm.write(f"Ken code : {kc} finished")

      f.write(f"[{kc}] 下記のメッシュコードがすでに存在しているためスキップしました:\n")
      for mesh in existing_files:
        f.write(mesh + "\n")
      f.write("\n\n")

if __name__ == "__main__":
  main()
