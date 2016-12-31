from flask import session, has_request_context

langs = [
    ('af', 'Afrikaans', 'Afrikaans'),
    ('als', 'Alemannisch', 'Alemannic'),
    ('am', 'አማርኛ', 'Amharic'),
    ('an', 'aragonés', 'Aragonese'),
    ('ar', 'العربية', 'Arabic'),
    ('arz', 'مصرى', 'Egyptian Arabic'),
    ('ast', 'asturianu', 'Asturian'),
    ('az', 'azərbaycanca', 'Azerbaijani'),
    ('azb', 'تۆرکجه', 'Southern Azerbaijani'),
    ('ba', 'башҡортса', 'Bashkir'),
    ('bar', 'Boarisch', 'Bavarian'),
    ('bat-smg', 'žemaitėška', 'Samogitian'),
    ('be', 'беларуская', 'Belarusian'),
    ('be-tarask', 'беларуская (тарашкевіца)', 'Belarusian (Taraškievica)'),
    ('bg', 'български', 'Bulgarian'),
    ('bn', 'বাংলা', 'Bengali'),
    ('bpy', 'বিষ্ণুপ্রিয়া মণিপুরী', 'Bishnupriya Manipuri'),
    ('br', 'brezhoneg', 'Breton'),
    ('bs', 'bosanski', 'Bosnian'),
    ('bug', 'ᨅᨔ ᨕᨘᨁᨗ', 'Buginese'),
    ('ca', 'català', 'Catalan'),
    ('ce', 'нохчийн', 'Chechen'),
    ('ceb', 'Cebuano', 'Cebuano'),
    ('ckb', 'کوردیی ناوەندی', 'Kurdish (Sorani)'),
    ('cs', 'čeština', 'Czech'),
    ('cv', 'Чӑвашла', 'Chuvash'),
    ('cy', 'Cymraeg', 'Welsh'),
    ('da', 'dansk', 'Danish'),
    ('de', 'Deutsch', 'German'),
    ('el', 'Ελληνικά', 'Greek'),
    ('en', 'English', 'English'),
    ('eo', 'Esperanto', 'Esperanto'),
    ('es', 'español', 'Spanish'),
    ('et', 'eesti', 'Estonian'),
    ('eu', 'euskara', 'Basque'),
    ('fa', 'فارسی', 'Persian'),
    ('fi', 'suomi', 'Finnish'),
    ('fo', 'føroyskt', 'Faroese'),
    ('fr', 'français', 'French'),
    ('fy', 'Frysk', 'West Frisian'),
    ('ga', 'Gaeilge', 'Irish'),
    ('gd', 'Gàidhlig', 'Scottish Gaelic'),
    ('gl', 'galego', 'Galician'),
    ('gu', 'ગુજરાતી', 'Gujarati'),
    ('he', 'עברית', 'Hebrew'),
    ('hi', 'हिन्दी', 'Hindi'),
    ('hr', 'hrvatski', 'Croatian'),
    ('hsb', 'hornjoserbsce', 'Upper Sorbian'),
    ('ht', 'Kreyòl ayisyen', 'Haitian'),
    ('hu', 'magyar', 'Hungarian'),
    ('hy', 'Հայերեն', 'Armenian'),
    ('ia', 'interlingua', 'Interlingua'),
    ('id', 'Bahasa Indonesia', 'Indonesian'),
    ('io', 'Ido', 'Ido'),
    ('is', 'íslenska', 'Icelandic'),
    ('it', 'italiano', 'Italian'),
    ('ja', '日本語', 'Japanese'),
    ('jv', 'Basa Jawa', 'Javanese'),
    ('ka', 'ქართული', 'Georgian'),
    ('kk', 'қазақша', 'Kazakh'),
    ('kn', 'ಕನ್ನಡ', 'Kannada'),
    ('ko', '한국어', 'Korean'),
    ('ku', 'Kurdî', 'Kurdish (Kurmanji)'),
    ('ky', 'Кыргызча', 'Kirghiz'),
    ('la', 'Latina', 'Latin'),
    ('lb', 'Lëtzebuergesch', 'Luxembourgish'),
    ('li', 'Limburgs', 'Limburgish'),
    ('lmo', 'lumbaart', 'Lombard'),
    ('lt', 'lietuvių', 'Lithuanian'),
    ('lv', 'latviešu', 'Latvian'),
    ('map-bms', 'Basa Banyumasan', 'Banyumasan'),
    ('mg', 'Malagasy', 'Malagasy'),
    ('min', 'Baso Minangkabau', 'Minangkabau'),
    ('mk', 'македонски', 'Macedonian'),
    ('ml', 'മലയാളം', 'Malayalam'),
    ('mn', 'монгол', 'Mongolian'),
    ('mr', 'मराठी', 'Marathi'),
    ('mrj', 'кырык мары', 'Hill Mari'),
    ('ms', 'Bahasa Melayu', 'Malay'),
    ('my', 'မြန်မာဘာသာ', 'Burmese'),
    ('mzn', 'مازِرونی', 'Mazandarani'),
    ('nah', 'Nāhuatl', 'Nahuatl'),
    ('nap', 'Napulitano', 'Neapolitan'),
    ('nds', 'Plattdüütsch', 'Low Saxon'),
    ('ne', 'नेपाली', 'Nepali'),
    ('new', 'नेपाल भाषा', 'Newar'),
    ('nl', 'Nederlands', 'Dutch'),
    ('nn', 'norsk nynorsk', 'Norwegian (Nynorsk)'),
    ('no', 'norsk bokmål', 'Norwegian (Bokmål)'),
    ('oc', 'occitan', 'Occitan'),
    ('or', 'ଓଡ଼ିଆ', 'Oriya'),
    ('os', 'Ирон', 'Ossetian'),
    ('pa', 'ਪੰਜਾਬੀ', 'Eastern Punjabi'),
    ('pl', 'polski', 'Polish'),
    ('pms', 'Piemontèis', 'Piedmontese'),
    ('pnb', 'پنجابی', 'Western Punjabi'),
    ('pt', 'português', 'Portuguese'),
    ('qu', 'Runa Simi', 'Quechua'),
    ('ro', 'română', 'Romanian'),
    ('ru', 'русский', 'Russian'),
    ('sa', 'संस्कृतम्', 'Sanskrit'),
    ('sah', 'саха тыла', 'Sakha'),
    ('scn', 'sicilianu', 'Sicilian'),
    ('sco', 'Scots', 'Scots'),
    ('sh', 'srpskohrvatski / српскохрватски', 'Serbo-Croatian'),
    ('si', 'සිංහල', 'Sinhalese'),
    ('simple', 'Simple English', 'Simple English'),
    ('sk', 'slovenčina', 'Slovak'),
    ('sl', 'slovenščina', 'Slovenian'),
    ('sq', 'shqip', 'Albanian'),
    ('sr', 'српски / srpski', 'Serbian'),
    ('su', 'Basa Sunda', 'Sundanese'),
    ('sv', 'svenska', 'Swedish'),
    ('sw', 'Kiswahili', 'Swahili'),
    ('ta', 'தமிழ்', 'Tamil'),
    ('te', 'తెలుగు', 'Telugu'),
    ('tg', 'тоҷикӣ', 'Tajik'),
    ('th', 'ไทย', 'Thai'),
    ('tl', 'Tagalog', 'Tagalog'),
    ('tr', 'Türkçe', 'Turkish'),
    ('tt', 'татарча/tatarça', 'Tatar'),
    ('uk', 'українська', 'Ukrainian'),
    ('ur', 'اردو', 'Urdu'),
    ('uz', 'oʻzbekcha/ўзбекча', 'Uzbek'),
    ('vec', 'vèneto', 'Venetian'),
    ('vi', 'Tiếng Việt', 'Vietnamese'),
    ('vo', 'Volapük', 'Volapük'),
    ('wa', 'walon', 'Walloon'),
    ('war', 'Winaray', 'Waray'),
    ('yi', 'ייִדיש', 'Yiddish'),
    ('yo', 'Yorùbá', 'Yoruba'),
    ('zh', '中文', 'Chinese'),
    ('zh-min-nan', 'Bân-lâm-gú', 'Min Nan'),
    ('zh-yue', '粵語', 'Cantonese'),
]

def get_langs():
    return [dict(zip(('code', 'local', 'english'), l)) for l in langs]

def get_current_language():
    return session.get('current_lang', 'en') if has_request_context() else 'en'
