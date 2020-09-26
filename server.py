import asyncio
import os

from aiohttp import web
import aiofiles

INTERVAL_SECS = 1
ARCHIVE_DIR_PATH = os.path.join(os.getcwd(), 'test_photos')


async def archivate(request):
    archive_name = request.match_info.get('archive_hash')
    archive_path = os.path.join(ARCHIVE_DIR_PATH, archive_name)

    if not os.path.isdir(archive_path):
        async with aiofiles.open('404.html', mode='r') as error_file:
            error_contents = await error_file.read()
        return web.Response(text=error_contents, content_type='text/html')

    file_name = f'{archive_name}.zip'
    header_value = f'attachment; filename="{file_name}"'
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = header_value

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    command = f'zip -r -j - {archive_path}'
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE
    )

    while True:
        archived_data = await process.stdout.read(100 * 1024)
        if not archived_data:
            break

        # Отправляет клиенту очередную порцию ответа
        await response.write(archived_data)

    await process.wait()
    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate),
    ])
    web.run_app(app)
