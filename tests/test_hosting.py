import unittest
from scripts.hosting_start import hosting_settings


class HostingTests(unittest.TestCase):
    def config(self, **override):
        return dict(APP_PUBLIC_ORIGIN='https://pilot.example.com', APP_ADMIN_TOKEN='x'*48,
                    APP_DATA_DIR='/data', PORT='8000', **override)

    def test_render_domain_and_persistent_directory(self):
        env=self.config();env.pop('APP_PUBLIC_ORIGIN');env['RENDER_EXTERNAL_URL']='https://pilot.onrender.com'
        origin,port,directory=hosting_settings(env)
        self.assertEqual(origin,'https://pilot.onrender.com');self.assertEqual(port,8000)
        self.assertEqual(str(directory),'/data')

    def test_public_http_missing_secret_or_nonpersistent_path_rejected(self):
        for key,value in [('APP_PUBLIC_ORIGIN','http://example.com'),('APP_PUBLIC_ORIGIN','https://example.com/login'),('APP_ADMIN_TOKEN','short'),('APP_DATA_DIR','relative'),('PORT','70000')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                env=self.config();env[key]=value;hosting_settings(env)

    def test_untrusted_render_fallback_rejected(self):
        env=self.config();env.pop('APP_PUBLIC_ORIGIN');env['RENDER_EXTERNAL_URL']='https://pilot.onrender.com.evil.example'
        with self.assertRaises(ValueError):hosting_settings(env)
