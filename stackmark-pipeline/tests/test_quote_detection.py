import unittest

from pipeline import classify_url, parse_quoted_tweet_from_x_api_payload


class QuoteDetectionTests(unittest.TestCase):
    def test_parse_quoted_tweet_from_x_api_payload_with_username(self):
        payload = {
            "data": {
                "id": "2034769466433913082",
                "referenced_tweets": [
                    {"type": "quoted", "id": "2000000000000000000"},
                ],
            },
            "includes": {
                "tweets": [
                    {"id": "2000000000000000000", "author_id": "42"},
                ],
                "users": [
                    {"id": "42", "username": "quotedauthor"},
                ],
            },
        }

        result = parse_quoted_tweet_from_x_api_payload(payload)

        self.assertTrue(result["is_quote_tweet"])
        self.assertEqual(result["quoted_tweet_id"], "2000000000000000000")
        self.assertEqual(
            result["quoted_tweet_url"],
            "https://x.com/quotedauthor/status/2000000000000000000",
        )
        self.assertEqual(result["quoted_username"], "quotedauthor")

    def test_parse_quoted_tweet_from_x_api_payload_without_username(self):
        payload = {
            "data": {
                "id": "2034769466433913082",
                "referenced_tweets": [
                    {"type": "quoted", "id": "2000000000000000000"},
                ],
            },
            "includes": {
                "tweets": [
                    {"id": "2000000000000000000", "author_id": "42"},
                ],
                "users": [],
            },
        }

        result = parse_quoted_tweet_from_x_api_payload(payload)

        self.assertTrue(result["is_quote_tweet"])
        self.assertEqual(
            result["quoted_tweet_url"],
            "https://x.com/i/web/status/2000000000000000000",
        )
        self.assertEqual(result["quoted_username"], "")

    def test_parse_non_quote(self):
        payload = {
            "data": {"id": "2034769466433913082", "referenced_tweets": []},
            "includes": {},
        }

        result = parse_quoted_tweet_from_x_api_payload(payload)

        self.assertFalse(result["is_quote_tweet"])
        self.assertEqual(result["quoted_tweet_id"], "")
        self.assertEqual(result["quoted_tweet_url"], "")

    def test_classify_i_web_status_url(self):
        url = "https://x.com/i/web/status/2000000000000000000"
        result = classify_url(url)

        self.assertEqual(result["source"], "x")
        self.assertEqual(result["tweet_id"], "2000000000000000000")
        self.assertEqual(result["username"], "")


if __name__ == "__main__":
    unittest.main()
