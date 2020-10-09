import argparse
import asyncio
from itertools import count
import logging
import os

from aiohttp import web
import aiofiles


def get_console_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Enable detailed logs.'
    )
    parser.add_argument(
        '-g',
        '--chunk_gap',
        type=int,
        default=0,
        help='A gap between response chunks in seconds.'
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
    archive_name = request.match_info.get('archive_hash', '')
    archive_path = os.path.join(request.app['data_dir_path'], archive_name)

    if not os.path.isdir(archive_path) or not archive_name:
        logging.warning(f'Invalid archive requested: {archive_path}')
        async with aiofiles.open('404.html', mode='r') as error_file:
            error_contents = await error_file.read()
        return web.Response(
            status=404,
            text=error_contents,
            content_type='text/html'
        )

    file_name = f'{archive_name}.zip'
    header_value = f'attachment; filename="{file_name}"'
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = header_value

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    command = f'zip -r - .'
    process = await asyncio.create_subprocess_exec(
        *command.split(),
        stdout=asyncio.subprocess.PIPE,
        cwd=archive_path
    )

    try:
        for chunk_number in count():
            archived_data = await process.stdout.read(100 * 1024)
            if not archived_data:
                break

            logging.info(f'Sending archive chunk number {chunk_number}...')
            await response.write(archived_data)
            if request.app['chunk_gap']:
                await asyncio.sleep(request.app['chunk_gap'])
    except asyncio.CancelledError:
        logging.warning('Download was interrupted.')
        raise
    finally:
        try:
            process.kill()
            logging.info('zip was terminated.')
        except ProcessLookupError:
            pass
        await process.communicate()
        return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main():
    console_arguments = get_console_arguments()
    if console_arguments.verbose:
        logging.basicConfig(level=logging.DEBUG)
    chunk_gap = console_arguments.chunk_gap
    data_dir_path = console_arguments.data_path
    app = web.Application()
    app['chunk_gap'] = chunk_gap
    app['data_dir_path'] = data_dir_path
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
