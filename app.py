#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["aiohttp", "python-dotenv", "todoist-api-python", "html2text"]
# ///


import asyncio
import os
import html2text

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task, Attachment, Comment

from aiohttp import ClientSession

from dotenv import load_dotenv
load_dotenv()

def unpack(iter_or_iter_of_iters):
    for it in iter_or_iter_of_iters:
        yield from it


API_TOKEN = os.getenv("TODOIST_API_TOKEN")
DOWNLOAD_COOKIE = os.getenv("TODOIST_DOWNLOAD_COOKIE")
api = TodoistAPI(API_TOKEN)

def get_first_attachment(task : Task):
    first_comment_paginator = api.get_comments(task_id=task.id)
    if not first_comment_paginator:
        return None

    first_comment_page = next(first_comment_paginator)
    # first comment of a task generated from an email is the email itself in html
    if not first_comment_page:
        return None

    first_comment : Comment = first_comment_page[0]
    if not first_comment or not first_comment.attachment:
        return None
    return first_comment.attachment


async def download_attachment(attachment : Attachment):
    async with ClientSession(
        cookies={"todoistd": DOWNLOAD_COOKIE}
    ) as session:
        async with session.get(attachment.file_url) as resp:
            print(f"downloading attachment from {attachment.file_url}, status {resp.status}")
            if resp.status != 200:
                print(f"failed to download attachment {attachment.file_url}")
                return None
            content = await resp.read()
            return content

def html_to_text(html_content : str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html_content)

async def main():
    tasks : list[Task] = unpack(api.filter_tasks(query="created after: -30 days"))

    while True:
        for task in tasks:
            print(f"processing task {task.id}: {task.content}")
            if task.description:
                print(f"task {task.id} already has a description, skipping.")
                continue
            attachment = get_first_attachment(task)
            if not attachment:
                print(f"task {task.id} has no attachment, skipping.")
                continue
            content = await download_attachment(attachment)
            if not content:
                print(f"failed to download attachment {attachment.file_url}, skipping.")
                continue
            new_description = html_to_text(content.decode('utf-8', errors='ignore'))
            try:
                api.update_task(task.id, description=new_description)
                print(f"updated task {task.id} with attachment content.")
            except Exception as e:
                print(f"failed to update task {task.id}: {e}")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())