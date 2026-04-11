import sys
import json
import urllib.request
import threading
import re

# Global set to track video IDs and prevent duplicates across threads
seen_ids = set()
lock = threading.Lock()

# Mapping of keywords to YouTube's "sp" parameter (Search Parameters)
SP_FILTERS = {
    "short": "EgIYAQ%3D%3D",  # Under 4 minutes
    "long": "EgIYAg%3D%3D",  # Over 20 minutes
    "medium": "EgIYAw%3D%3D",  # 4-20 minutes
    "playlist": "EgIQAw%3D%3D",
    "channel": "EgIQAg%3D%3D",
    "movie": "EgIQBA%3D%3D",
    "creative": "EgIwAQ%3D%3D",
    "hd": "EgIgAQ%3D%3D",
    "4k": "EgIgFw%3D%3D",
    "cc": "EgIgAA%3D%3D",
    "live": "EgJAAQ%3D%3D",
    "360": "EgIgGQ%3D%3D",
    "hdr": "EgIgGw%3D%3D",
    "vr180": "EgIgHg%3D%3D",
    "hour": "EgQIARAB",
    "today": "EgQIAhAB",
    "week": "EgQIAxAB",
    "month": "EgQIBBAB",
    "year": "EgQIBhAB",
    "recent": "CAI%3D",
    "views": "CAM%3D",
    "rating": "CAE%3D",
}


def fetch_page(url, data):
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except:
        return None


def extract_continuation(res, is_initial):
    try:
        if is_initial:
            sections = (
                res.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
        else:
            sections = (
                res.get("onResponseReceivedCommands", [{}])[0]
                .get("appendContinuationItemsAction", {})
                .get("continuationItems", [])
            )

        for s in sections:
            cont = (
                s.get("continuationItemRenderer", {})
                .get("continuationEndpoint", {})
                .get("continuationCommand", {})
                .get("token")
            )
            if cont:
                return cont
    except:
        pass
    return None


def parse_duration_to_seconds(duration_str):
    if not duration_str:
        return 0
    # Strip non-numeric/colon chars (e.g. 'SHORTS')
    duration_str = re.sub(r"[^0-9:]", "", duration_str)
    if not duration_str:
        return 0
    parts = duration_str.split(":")
    try:
        if len(parts) == 3:  # H:M:S
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:  # M:S
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:  # S
            return int(parts[0])
    except:
        return 0
    return 0


def print_video(video, active_filter):
    video_id = video.get("videoId")
    if not video_id:
        return

    # Extract duration
    # standard videos have lengthText, compact (related) have lengthText or simpleText
    duration_text = video.get("lengthText", {}).get("simpleText", "")
    if not duration_text:
        # Some renderers nest it differently
        duration_text = (
            video.get("thumbnailOverlays", [{}])[0]
            .get("thumbnailOverlayTimeStatusRenderer", {})
            .get("text", {})
            .get("simpleText", "")
        )

    duration_sec = parse_duration_to_seconds(duration_text)

    # STRICT CLIENT-SIDE FILTERING
    if active_filter and active_filter.startswith("dur:"):
        try:
            bounds = active_filter.split(":")[1].split("-")
            min_s = int(bounds[0])
            max_s = float("inf") if bounds[1] == "inf" else int(bounds[1])
            if duration_sec < min_s or duration_sec > max_s:
                return
        except:
            pass
    elif active_filter == "short":
        if duration_sec == 0 or duration_sec >= 240:
            return
    elif active_filter == "long":
        if duration_sec <= 1200:
            return

    with lock:
        if video_id in seen_ids:
            return
        seen_ids.add(video_id)

    title = video.get("title", {}).get("runs", [{}])[0].get("text", video.get("title", {}).get("simpleText", "Unknown"))
    channel = (
        video.get("longBylineText", {})
        .get("runs", [{}])[0]
        .get("text", video.get("shortBylineText", {}).get("runs", [{}])[0].get("text", "Unknown"))
    )
    view_text = video.get("viewCountText", {})
    views = view_text.get("simpleText", view_text.get("runs", [{}])[0].get("text", "0")).split(" ")[0]
    published = video.get("publishedTimeText", {}).get("simpleText", "")

    badges = [b.get("metadataBadgeRenderer", {}).get("label", "") for b in video.get("badges", [])]
    badges = [b for b in badges if b]
    badge_str = f" [{', '.join(badges)}]" if badges else ""

    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        sys.stdout.write(f"{thumb}\t{title}{badge_str}\t{channel}\t{views} ({published}) [{duration_text}]\t{url}\n")
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def print_playlist(playlist):
    playlist_id = playlist.get("contentId")
    if not playlist_id:
        return

    with lock:
        if playlist_id in seen_ids:
            return
        seen_ids.add(playlist_id)

    meta_lvm = playlist.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = meta_lvm.get("title", {}).get("content", "Unknown")

    channel = "Unknown"
    try:
        channel = (
            meta_lvm.get("metadata", {})
            .get("contentMetadataViewModel", {})
            .get("metadataRows", [{}])[0]
            .get("metadataParts", [{}])[0]
            .get("text", {})
            .get("content", "Unknown")
        )
    except:
        pass

    video_count = ""
    try:
        video_count = (
            playlist.get("contentImage", {})
            .get("collectionThumbnailViewModel", {})
            .get("primaryThumbnail", {})
            .get("thumbnailViewModel", {})
            .get("overlays", [{}])[0]
            .get("thumbnailOverlayBadgeViewModel", {})
            .get("thumbnailBadges", [{}])[0]
            .get("thumbnailBadgeViewModel", {})
            .get("text", "")
        )
    except:
        pass

    thumb = ""
    try:
        thumb = (
            playlist.get("contentImage", {})
            .get("collectionThumbnailViewModel", {})
            .get("primaryThumbnail", {})
            .get("thumbnailViewModel", {})
            .get("image", {})
            .get("sources", [{}])[0]
            .get("url", "")
        )
        if thumb.startswith("//"):
            thumb = "https:" + thumb
    except:
        pass

    url = f"https://www.youtube.com/playlist?list={playlist_id}"

    try:
        sys.stdout.write(f"{thumb}\t[PLAYLIST] {title}\t{channel}\t{video_count}\t{url}\n")
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def print_channel(channel_data):
    channel_id = channel_data.get("channelId")
    if not channel_id:
        return

    with lock:
        if channel_id in seen_ids:
            return
        seen_ids.add(channel_id)

    title = channel_data.get("title", {}).get("simpleText", "Unknown")

    handle = channel_data.get("subscriberCountText", {}).get("simpleText", "")
    subs = channel_data.get("videoCountText", {}).get("simpleText", "")

    thumb = ""
    try:
        thumb = channel_data.get("thumbnail", {}).get("thumbnails", [{}])[0].get("url", "")
        if thumb.startswith("//"):
            thumb = "https:" + thumb
    except:
        pass

    url = f"https://www.youtube.com/channel/{channel_id}"

    try:
        sys.stdout.write(f"{thumb}\t[CHANNEL] {title}\t{handle}\t{subs}\t{url}\n")
        sys.stdout.flush()
    except BrokenPipeError:
        sys.exit(0)


def process_results(res, is_initial, active_filter):
    if not res:
        return
    if is_initial:
        contents = (
            res.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
    else:
        contents = (
            res.get("onResponseReceivedCommands", [{}])[0]
            .get("appendContinuationItemsAction", {})
            .get("continuationItems", [])
        )

    for section in contents:
        # Check for direct video (common in continuations)
        if "videoRenderer" in section:
            print_video(section["videoRenderer"], active_filter)
            continue
        elif "lockupViewModel" in section:
            print_playlist(section["lockupViewModel"])
            continue
        elif "channelRenderer" in section:
            print_channel(section["channelRenderer"])
            continue

        # Check for itemSectionRenderer
        item_section = section.get("itemSectionRenderer", {}).get("contents", [])
        for item in item_section:
            video = item.get("videoRenderer")
            if video:
                print_video(video, active_filter)
            elif "lockupViewModel" in item:
                print_playlist(item["lockupViewModel"])
            elif "channelRenderer" in item:
                print_channel(item["channelRenderer"])
            else:
                # Handle shelves (People also watched, etc)
                shelf = (
                    item.get("shelfRenderer", {}).get("content", {}).get("verticalListRenderer", {}).get("items", [])
                )
                for shelf_item in shelf:
                    v = shelf_item.get("videoRenderer")
                    if v:
                        print_video(v, active_filter)


def worker(query, params, active_filter, url, context):
    data = {"context": context, "query": query}
    if params:
        data["params"] = params
    res = fetch_page(url, data)
    if not res:
        return
    process_results(res, True, active_filter)
    continuation = extract_continuation(res, True)
    while continuation:
        data = {"context": context, "continuation": continuation}
        res = fetch_page(url, data)
        if not res:
            break
        process_results(res, False, active_filter)
        continuation = extract_continuation(res, False)


def parse_query(raw_query):
    parts = raw_query.split(" --flags ")
    query_text = parts[0]
    flags = parts[1].split(",") if len(parts) > 1 else []

    sp = None
    active_filter = None

    # Check if we should apply a sort filter in addition to duration
    sort_sp = None

    for f in flags:
        if f.startswith("dur:"):
            active_filter = f
            try:
                bounds = f.split(":")[1].split("-")
                min_s = int(bounds[0])
                max_s = float("inf") if bounds[1] == "inf" else int(bounds[1])
                # Apply the closest native YouTube filter to speed up client-side filtering
                if max_s <= 240:
                    sp = SP_FILTERS["short"]
                elif min_s >= 1200:
                    # If looking for very long videos, sort by duration to find them faster
                    sp = "EgIQAQ%3D%3D"  # Sort by Duration (longest first)
                elif min_s >= 240 and max_s <= 1200:
                    sp = SP_FILTERS["medium"]
            except:
                pass
            break
        elif f in SP_FILTERS:
            sp = SP_FILTERS[f]
            active_filter = f
            break

    if not sp:
        for kw, val in SP_FILTERS.items():
            pattern = rf"[, ]+\b{kw}\b\s*$"
            if re.search(pattern, query_text, re.IGNORECASE):
                sp = val
                active_filter = kw
                query_text = re.sub(pattern, "", query_text, flags=re.IGNORECASE).strip()
                break
    return query_text, sp, active_filter


def search(raw_query):
    query_text, sp, active_filter = parse_query(raw_query)

    if query_text.startswith("related:"):
        video_id = query_text.replace("related:", "").strip()
        url = "https://www.youtube.com/youtubei/v1/next"
        context = {"client": {"clientName": "WEB", "clientVersion": "2.20240320.01.00"}}
        data = {"context": context, "videoId": video_id}
        res = fetch_page(url, data)
        if res:
            results = (
                res.get("contents", {})
                .get("twoColumnWatchNextResults", {})
                .get("secondaryResults", {})
                .get("secondaryResults", {})
                .get("results", [])
            )
            for r in results:
                if "compactVideoRenderer" in r:
                    print_video(r["compactVideoRenderer"], None)
                elif "lockupViewModel" in r:
                    # Related videos now use lockupViewModel too
                    # We can try to print it as a video if it has video metadata
                    lvm = r["lockupViewModel"]
                    content_id = lvm.get("contentId")
                    if not content_id:
                        continue

                    # Check if it's a video by looking for duration or video-specific badges
                    is_video = True
                    if "collectionThumbnailViewModel" in lvm.get("contentImage", {}):
                        is_video = False  # It's a playlist

                    if is_video:
                        # Construct a fake videoRenderer object to pass to print_video
                        # or just extract here. Let's extract here since it's simpler
                        with lock:
                            if content_id in seen_ids:
                                continue
                            seen_ids.add(content_id)

                        meta_lvm = lvm.get("metadata", {}).get("lockupMetadataViewModel", {})
                        title = meta_lvm.get("title", {}).get("content", "Unknown")

                        channel = "Unknown"
                        try:
                            channel = (
                                meta_lvm.get("metadata", {})
                                .get("contentMetadataViewModel", {})
                                .get("metadataRows", [{}])[0]
                                .get("metadataParts", [{}])[0]
                                .get("text", {})
                                .get("content", "Unknown")
                            )
                        except:
                            pass

                        views = ""
                        try:
                            views = (
                                meta_lvm.get("metadata", {})
                                .get("contentMetadataViewModel", {})
                                .get("metadataRows", [{}])[1]
                                .get("metadataParts", [{}])[0]
                                .get("text", {})
                                .get("content", "")
                            )
                        except:
                            pass

                        published = ""
                        try:
                            published = (
                                meta_lvm.get("metadata", {})
                                .get("contentMetadataViewModel", {})
                                .get("metadataRows", [{}])[1]
                                .get("metadataParts", [{}])[1]
                                .get("text", {})
                                .get("content", "")
                            )
                        except:
                            pass

                        duration = ""
                        try:
                            # Try multiple paths for duration in lockupViewModel
                            duration = (
                                lvm.get("contentImage", {})
                                .get("imageThumbnailViewModel", {})
                                .get("image", {})
                                .get("overlays", [{}])[0]
                                .get("thumbnailOverlayTimeStatusRenderer", {})
                                .get("text", {})
                                .get("simpleText", "")
                            )
                            if not duration:
                                duration = (
                                    lvm.get("contentImage", {})
                                    .get("imageThumbnailViewModel", {})
                                    .get("image", {})
                                    .get("overlays", [{}])[0]
                                    .get("thumbnailOverlayBottomRightViewModel", {})
                                    .get("text", {})
                                    .get("content", "")
                                )
                            if not duration:
                                duration = (
                                    lvm.get("contentImage", {})
                                    .get("thumbnailViewModel", {})
                                    .get("overlays", [{}])[0]
                                    .get("thumbnailBottomOverlayViewModel", {})
                                    .get("badges", [{}])[0]
                                    .get("thumbnailBadgeViewModel", {})
                                    .get("text", "")
                                )
                        except:
                            pass

                        thumb = f"https://i.ytimg.com/vi/{content_id}/hqdefault.jpg"
                        url = f"https://www.youtube.com/watch?v={content_id}"

                        try:
                            sys.stdout.write(
                                f"{thumb}\t{title}\t{channel}\t{views} ({published}) [{duration}]\t{url}\n"
                            )
                            sys.stdout.flush()
                        except BrokenPipeError:
                            sys.exit(0)
                    else:
                        print_playlist(lvm)
        return

    url = "https://www.youtube.com/youtubei/v1/search"
    context = {"client": {"clientName": "WEB", "clientVersion": "2.20240320.01.00"}}

    t1 = threading.Thread(target=worker, args=(query_text, sp, active_filter, url, context))
    t2 = threading.Thread(target=worker, args=(f"{query_text} ", sp, active_filter, url, context))
    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        search(sys.argv[1])
