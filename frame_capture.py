import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import astral
import astral.geocoder as geocoder
from astral.sun import sun

import cv2

from stw2xml import generate_timed_xml, generate_xml


def get_location_sun_times(location: str, date: datetime) -> dict:
    city: astral.LocationInfo = geocoder.lookup(location, geocoder.database())
    return sun(city.observer, date), city.timezone


class VideoTime(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        values = values.split(":")
        if len(values) < 2 or len(values) > 4:
            raise argparse.ArgumentTypeError(
                "Invalid time format. Use: HH:MM[:SS[:ms]]"
            )
        multiplier = 3600
        video_time = 0
        try:
            for value in values:
                video_time += int(value) * multiplier
                multiplier /= 60
        except ValueError:
            raise argparse.ArgumentTypeError(
                "Invalid time format. Use: HH:MM[:SS[:ms]]"
            )
        setattr(namespace, self.dest, video_time)


def round_seconds(obj: datetime) -> datetime:
    if obj.microsecond >= 500_000:
        obj += timedelta(seconds=1)
    return obj.replace(microsecond=0)


def main():
    parser = argparse.ArgumentParser(
        description="Capture frames from a video file into GNOME dynamic panorama XML."
    )
    parser.add_argument(
        "input_video",
        help="Path to the input video file",
        type=Path,
    )
    parser.add_argument(
        "start_time",
        help="Start time of the video in the format HH:MM[:SS[:ms]]",
        action=VideoTime,
    )
    parser.add_argument(
        "end_time",
        help="End time of the video in the format HH:MM[:SS[:ms]]",
        action=VideoTime,
    )
    parser.add_argument(
        "--working_dir",
        "-w",
        help="Working directory for the output files",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--skip-frames",
        "-s",
        help="Number of frames to skip after the start time",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--num-frames",
        "-n",
        help="Number of frames to capture",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--location",
        help="Your current location",
        type=str,
        default="Atlanta",
    )
    parser.add_argument(
        "--dawn-frame",
        help="The frame on which dawn starts",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--dusk-frame",
        help="The frame on which dusk starts (ignored if --mirror is set)",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--sunrise-frame",
        help="The frame on which the sun rises (and corresponding sun sets)",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--sunset-frame",
        help="The frame on which the sun sets (ignored if --mirror is set)",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--csv",
        help="Generate a simple csv file in addition to an XML file",
        action="store_true",
    )
    parser.add_argument(
        "--mirror",
        help="Mirror the video from noon to midnight",
        action="store_true",
    )
    parser.add_argument(
        "--no-write",
        help="Do not write new video frames",
        action="store_true",
    )

    args = parser.parse_args()
    video_path: Path = args.input_video
    start_time: datetime = args.start_time
    end_time: datetime = args.end_time
    work_folder: Path = args.working_dir
    num_skip: int = args.skip_frames
    num_frames: int = args.num_frames
    location: str = args.location
    dawn_frame: int = args.dawn_frame
    dusk_frame: int = args.dusk_frame
    sunrise_frame: int = args.sunrise_frame
    sunset_frame: int = args.sunset_frame

    wallpaper_name = video_path.stem

    video = cv2.VideoCapture(str(video_path))
    fps = video.get(cv2.CAP_PROP_FPS)

    start_frame_index = int(start_time * fps) + num_skip
    video.set(cv2.CAP_PROP_POS_FRAMES, start_frame_index)
    end_frame_index = (
        start_frame_index + num_frames
        if num_frames > 0
        else int((end_time - start_time).total_seconds() * fps)
    )

    def mirrored_frame_index(frame_index: int) -> int:
        return start_frame_index + num_frames * 2 - frame_index

    current = start_frame_index
    pics = []
    end_pics = []
    while current <= end_frame_index:
        print(f"{current-start_frame_index:03d}/{num_frames}", end="\r")
        ret, frame = video.read() if not args.no_write else (True, None)
        if ret:
            pic_path = work_folder.joinpath(
                f"{wallpaper_name}-{current-start_frame_index:03d}.jpg"
            )
            pics.append(pic_path)
            if not args.no_write:
                cv2.imwrite(str(pic_path), frame)
            if args.mirror:
                mirrored_index = mirrored_frame_index(current)
                if (
                    start_frame_index != current and mirrored_index != current
                ):  # Skip the endpoints
                    pic_path = work_folder.joinpath(
                        f"{wallpaper_name}-{mirrored_index:03d}.jpg"
                    )
                    end_pics.append(pic_path)
                    if not args.no_write:
                        cv2.imwrite(str(pic_path), frame)
            current += 1
        else:
            break
    pics.extend(reversed(end_pics))
    video.release()
    timed_pics = []
    now = datetime.now()
    start_time = datetime(now.year, now.month, now.day)
    if dawn_frame > 0 or sunrise_frame > 0:
        sun_times, timezone = get_location_sun_times(location, start_time)
        timezone = ZoneInfo(timezone)
        start_time = start_time.replace(tzinfo=timezone)
        end_time = start_time + timedelta(days=1)
        dawn_time = sun_times["dawn"].astimezone(timezone)
        sunrise_time = sun_times["sunrise"].astimezone(timezone)
        noon_time = sun_times["noon"].astimezone(timezone)
        sunset_time = sun_times["sunset"].astimezone(timezone)
        dusk_time = sun_times["dusk"].astimezone(timezone)
        noon_frame = len(pics) // 2
        sunset_frame = (
            mirrored_frame_index(sunrise_frame + start_frame_index)
            if args.mirror
            else sunset_frame
        )
        dusk_frame = (
            mirrored_frame_index(dawn_frame + start_frame_index)
            if args.mirror
            else dusk_frame
        )
        print(f"Timezone: {timezone}")
        print(f"Start time: {start_time}, frame: 0")
        print(f"Dawn time: {dawn_time}, frame: {dawn_frame}")
        print(f"Sunrise time: {sunrise_time}, frame: {sunrise_frame}")
        print(f"Noon time: {noon_time}, frame: {noon_frame}")
        print(f"Sunset time: {sunset_time}, frame: {sunset_frame}")
        print(f"Dusk time: {dusk_time}, frame: {dusk_frame}")
        print(f"End time: {end_time}, frame: {len(pics)-1}")
        first_night_frames = pics[:dawn_frame]
        night_duration = (dawn_time - start_time) / len(first_night_frames)
        for index, pic_path in enumerate(first_night_frames):
            pic_time = round_seconds(start_time + night_duration * index)
            timed_pics.append((pic_time, pic_path))
        dawn_frames = pics[dawn_frame:sunrise_frame]
        dawn_duration = (sunrise_time - dawn_time) / len(dawn_frames)
        for index, pic_path in enumerate(dawn_frames):
            pic_time = round_seconds(dawn_time + dawn_duration * index)
            timed_pics.append((pic_time, pic_path))
        first_day_frames = pics[sunrise_frame:noon_frame]
        first_day_duration = (noon_time - sunrise_time) / len(first_day_frames)
        for index, pic_path in enumerate(first_day_frames):
            pic_time = round_seconds(sunrise_time + first_day_duration * index)
            timed_pics.append((pic_time, pic_path))
        second_day_frames = pics[noon_frame:sunset_frame]
        second_day_duration = (sunset_time - noon_time) / len(second_day_frames)
        for index, pic_path in enumerate(second_day_frames):
            pic_time = round_seconds(noon_time + second_day_duration * index)
            timed_pics.append((pic_time, pic_path))
        dusk_frames = pics[sunset_frame:dusk_frame]
        dusk_duration = (dusk_time - sunset_time) / len(dusk_frames)
        for index, pic_path in enumerate(dusk_frames):
            pic_time = round_seconds(sunset_time + dusk_duration * index)
            timed_pics.append((pic_time, pic_path))
        second_night_frames = pics[dusk_frame:]
        night_duration = (end_time - dusk_time) / len(second_night_frames)
        for index, pic_path in enumerate(second_night_frames):
            pic_time = round_seconds(dusk_time + night_duration * index)
            timed_pics.append((pic_time, pic_path))
    else:
        pic_duration = timedelta(days=1) / len(pics)
        for index, pic_path in enumerate(pics):
            pic_time = round_seconds(start_time + pic_duration * index)
            timed_pics.append((pic_time, pic_path))
    if args.csv:
        with open(work_folder.joinpath(f"{wallpaper_name}.csv"), "w") as f:
            for pic_time, pic_path in timed_pics:
                f.write(f"'{pic_time.strftime('%H:%M:%S')}','{pic_path}'\n")
    path_to_timed_xml = generate_timed_xml(wallpaper_name, timed_pics, work_folder)
    generate_xml(wallpaper_name, path_to_timed_xml, work_folder)


if __name__ == "__main__":
    main()
