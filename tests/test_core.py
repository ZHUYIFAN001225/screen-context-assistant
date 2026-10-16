import unittest
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QRect

import account_backend
from screen_capture import physical_region


class CoordinateTests(unittest.TestCase):
    def test_scaled_selection(self):
        result = physical_region(QRect(100, 60, 80, 40), QRect(0, 0, 1280, 720),
                                 1.5, {'left': 0, 'top': 0, 'width': 1920, 'height': 1080})
        self.assertEqual(result, {'left': 150, 'top': 90, 'width': 120, 'height': 60})

    def test_negative_monitor_origin(self):
        result = physical_region(QRect(-1200, 40, 100, 80), QRect(-1280, 0, 1280, 720),
                                 1, {'left': -1280, 'top': 0, 'width': 1280, 'height': 720})
        self.assertEqual(result, {'left': -1200, 'top': 40, 'width': 100, 'height': 80})

    def test_right_bottom_clamping(self):
        result = physical_region(QRect(1260, 700, 40, 40), QRect(0, 0, 1280, 720),
                                 1.5, {'left': 0, 'top': 0, 'width': 1920, 'height': 1080})
        self.assertEqual(result, {'left': 1890, 'top': 1050, 'width': 30, 'height': 30})


class FakeConnection:
    ephemeral = True
    events = []
    instance = None

    def __init__(self, cwd):
        type(self).instance = self
        self.calls = []
        self.buffered = list(type(self).events)
        self.closed = False

    def request(self, method, params):
        self.calls.append((method, params))
        if method == 'account/read':
            return {'account': {'type': 'chatgpt'}}
        if method == 'thread/start':
            return {'thread': {'id': 'synthetic-thread', 'ephemeral': type(self).ephemeral}}
        return {}

    def send(self, message):
        self.calls.append(('notification', message))

    def next_message(self):
        raise AssertionError('Unexpected wait in offline test')

    def close(self):
        self.closed = True


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.ephemeral = True
        FakeConnection.events = [
            {'method': 'item/completed', 'params': {'threadId': 'synthetic-thread',
             'item': {'type': 'agentMessage', 'id': 'answer', 'text': 'synthetic result'}}},
            {'method': 'turn/completed', 'params': {'threadId': 'synthetic-thread',
             'turn': {'status': 'completed'}}},
        ]

    def analyze(self):
        with patch.object(account_backend, 'AccountConnection', FakeConnection):
            return account_backend.analyze_with_account(Image.new('RGB', (2, 2), 'red'),
                                                        'Explain the synthetic image', '.')

    def test_success_uses_image_and_ephemeral_read_only_thread(self):
        self.assertEqual(self.analyze(), 'synthetic result')
        calls = dict(FakeConnection.instance.calls)
        self.assertTrue(calls['thread/start']['ephemeral'])
        self.assertEqual(calls['thread/start']['approvalPolicy'], 'never')
        self.assertEqual(calls['thread/start']['sandbox'], 'read-only')
        picture = calls['turn/start']['input'][1]
        self.assertEqual(picture['type'], 'image')
        self.assertTrue(picture['url'].startswith('data:image/png;base64,'))
        self.assertTrue(FakeConnection.instance.closed)

    def test_refuses_non_ephemeral_thread_before_sending_image(self):
        FakeConnection.ephemeral = False
        with self.assertRaisesRegex(RuntimeError, '临时分析会话'):
            self.analyze()
        self.assertFalse(any(method == 'turn/start' for method, _ in FakeConnection.instance.calls))
        self.assertTrue(FakeConnection.instance.closed)

    def test_refuses_tool_execution(self):
        FakeConnection.events.insert(0, {'method': 'item/completed', 'params': {
            'threadId': 'synthetic-thread', 'item': {'type': 'commandExecution'}}})
        with self.assertRaisesRegex(RuntimeError, '额外工具'):
            self.analyze()
        self.assertTrue(FakeConnection.instance.closed)

    def test_does_not_treat_failed_turn_as_success(self):
        FakeConnection.events[-1]['params']['turn'] = {
            'status': 'failed', 'error': {'message': 'usage limit reached'}}
        with self.assertRaisesRegex(RuntimeError, '额度'):
            self.analyze()
        self.assertTrue(FakeConnection.instance.closed)


if __name__ == '__main__':
    unittest.main()
