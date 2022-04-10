from io import TextIOWrapper
from datetime import datetime, timedelta
from os import path
import sys

from lxml import etree

DEFAULT_TRANSITION_DURATION = 5.0


def index_to_jpg_path(name: str, pic_folder_path: str, index: int):
    return path.join(pic_folder_path, f"{name}-{index+1}.jpg")


def read_stw(file: TextIOWrapper, pic_folder_path):
    _ver = file.readline().split(": ")[1]
    name = file.readline().split(": ")[1].strip()
    _format = file.readline().split(": ")[1]
    pics = []
    for line in file.readlines():
        time, index = line.split(": ")
        now = datetime.now()
        hour, minute = time[1:].split(":")
        time = datetime(now.year, now.month, now.day, int(hour), int(minute))
        pics.append((time, index_to_jpg_path(name, pic_folder_path, int(index))))
    return name, pics


def generate_xml(name: str, timed_xml_path: str, xml_out_path: str):
    wallpapers = etree.Element("wallpapers")
    wallpaper = etree.SubElement(wallpapers, "wallpaper", {"deleted": "false"})
    etree.SubElement(wallpaper, "name").text = name
    etree.SubElement(wallpaper, "filename").text = timed_xml_path
    etree.SubElement(wallpaper, "options").text = "zoom"
    etree.SubElement(wallpaper, "shade_type").text = "solid"
    etree.SubElement(wallpaper, "pcolor").text = "#ffffff"
    etree.SubElement(wallpaper, "scolor").text = "#000000"
    tree = etree.ElementTree(wallpapers)
    xml_path = path.join(xml_out_path, f"{name}.xml")
    tree.write(xml_path, pretty_print=True, encoding="utf-8")


def generate_timed_xml(
    name: str,
    pics: list,
    xml_out_path: str,
    transition_duration=DEFAULT_TRANSITION_DURATION,
):
    start_time: datetime = pics[0][0]
    end_time = start_time + timedelta(days=1)
    pics_duration = []
    total_duration = timedelta()
    for i in range(1, len(pics)):
        start, fr = pics[i - 1]
        end, to = pics[i]
        total_duration += end - start
        duration_secs = float((end - start).total_seconds())
        pics_duration.append((duration_secs, fr, to))
    total_duration += end_time - pics[-1][0]
    pics_duration.append(
        ((end_time - pics[-1][0]).total_seconds(), pics[-1][1], pics[0][1])
    )
    print(f"Total duration: {total_duration}")
    background = etree.Element("background")
    starttime = etree.SubElement(background, "starttime")
    etree.SubElement(starttime, "year").text = str(start_time.year)
    etree.SubElement(starttime, "month").text = str(start_time.month)
    etree.SubElement(starttime, "day").text = str(start_time.day)
    etree.SubElement(starttime, "hour").text = str(start_time.hour)
    etree.SubElement(starttime, "minute").text = str(start_time.minute)
    etree.SubElement(starttime, "second").text = str(start_time.second)
    for duration, fr, to in pics_duration:
        static = etree.SubElement(background, "static")
        etree.SubElement(static, "file").text = str(fr)
        etree.SubElement(static, "duration").text = str(duration)
        transition = etree.SubElement(background, "transition", {"type": "overlay"})
        etree.SubElement(transition, "duration").text = str(transition_duration)
        etree.SubElement(transition, "from").text = str(fr)
        etree.SubElement(transition, "to").text = str(to)
    tree = etree.ElementTree(background)
    timed_xml_path = path.join(xml_out_path, f"{name}-timed.xml")
    tree.write(timed_xml_path, pretty_print=True, encoding="utf-8")
    return timed_xml_path


def main():
    stw_file_path = sys.argv[1]
    work_folder = sys.argv[2]
    with open(stw_file_path, mode="r") as file:
        name, pics = read_stw(file, work_folder)
        timed_xml_path = generate_timed_xml(name, pics, work_folder)
        generate_xml(name, timed_xml_path, work_folder)


if __name__ == "__main__":
    main()
