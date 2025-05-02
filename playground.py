import deepl
import creds

translator = deepl.Translator(creds.auth_key)

result = translator.translate_text("Hello, world!", target_lang="DE")
print(result.text)