import argparse
import asyncio
import logging
import os

from aiohttp import web
import aiofiles

INTERVAL_SECS = 1
ARCHIVE_DIR_PATH = os.path.join(os.getcwd(), 'test_photos')


def get_console_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v',
        action='store_true',
        help='Enable detailed logs.'
    )
    parser.add_argument(
        '-t',
        '--response_timeout',
        type=int,
        default=0,
        help='Response timeout in seconds.'
    )
    parser.add_argument(
        '-p',
        '--data_path',
        required=True,
        type=str,
        help='A path to data the server should send to clients.'
    )
    inputted_arguments = parser.parse_args()
    return inputted_arguments


async def archive(request):
    archive_name = request.match_info.get('archive_hash')
    archive_path = os.path.join(ARCHIVE_DIR_PATH, archive_name)

    if not os.path.isdir(archive_path):
        logging.warning(f'Invalid archive requested: {archive_path}')
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

    chunk_number = 0
    try:
        while True:
            chunk_number += 1
            archived_data = await process.stdout.read(100 * 1024)
            if not archived_data:
                break

            logging.info(f'Sending archive chunk number {chunk_number}...')
            await response.write(archived_data)
    except asyncio.CancelledError:
        logging.warning('Download was interrupted.')
        process.kill()
        logging.info('zip was terminated')
    finally:
        await process.communicate()
        return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    console_arguments = get_console_arguments()
    logging.basicConfig(level=logging.INFO)
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
