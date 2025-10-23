"""Test your internet speed using lite"""
import asyncio
import speedtest as st

async def speed_test_async():
    """Asynchronous speed test function using asyncio.to_thread"""
    print('Starting speed test...')

    test = st.Speedtest()

    await asyncio.to_thread(test.get_best_server)

    print('Testing download speed...')
    down_speed = await asyncio.to_thread(test.download)
    down_speed_mbps = round(down_speed / 10**6, 2)
    print(f'Download Speed: {down_speed_mbps}Mbps')

    print('Testing upload speed...')
    up_speed = await asyncio.to_thread(test.upload)
    up_speed_mbps = round(up_speed / 10**6, 2)
    print(f'Upload Speed: {up_speed_mbps}Mbps')

    ping = test.results.ping
    print('Ping:', ping)

if __name__ == "__main__":
    asyncio.run(speed_test_async())
