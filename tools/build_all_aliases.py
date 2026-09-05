# Build comprehensive aliases mapping for all Pakistan districts, tehsils, and Urdu variants
import csv
import json
from pathlib import Path

DATA_DIR = Path('data')

# Load gazetteer to get all valid adm2 districts and adm3 tehsils
with open(DATA_DIR / 'pak_gazetteer.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

valid_districts = set(r['adm2_name'].strip() for r in rows)

# Base dictionary: load current aliases.json
with open(DATA_DIR / 'aliases.json', encoding='utf-8') as f:
    aliases = json.load(f)

# 1. Add all tehsils from gazetteer (adm3_name -> adm2_name)
for r in rows:
    tehsil = r['adm3_name'].strip()
    district = r['adm2_name'].strip()
    if district in valid_districts:
        k = tehsil.lower()
        if k not in aliases and k != district.lower():
            aliases[k] = district

# 2. Comprehensive Urdu and Roman variants for all 160 districts
URDU_MAP = {
    # Punjab
    'Attock': ['اٹک', 'ضلع اٹک', 'attak'],
    'Bahawalnagar': ['بہاولنگر', 'بہاول نگر', 'bahawal nagar'],
    'Bahawalpur': ['بہاولپور', 'بہاول پور', 'bahawal pur'],
    'Bhakkar': ['بھکر', 'ضلع بھکر'],
    'Chakwal': ['چکوال', 'ضلع چکوال'],
    'Chiniot': ['چنیوٹ', 'ضلع چنیوٹ'],
    'Dera Ghazi Khan': ['ڈیرہ غازی خان', 'ڈی جی خان', 'dera ghazi khan', 'dg khan', 'd.g khan', 'd.g. khan', 'deraghazikhan'],
    'Faisalabad': ['فیصل آباد', 'فیصل اباد', 'لائلپور', 'faisal abad', 'lyallpur'],
    'Gujranwala': ['گوجرانوالہ', 'گوجرانوالا', 'gujran wala'],
    'Gujrat': ['گجرات', 'ضلع گجرات'],
    'Hafizabad': ['حافظ آباد', 'حافظ اباد', 'hafiz abad'],
    'Jhang': ['جھنگ', 'ضلع جھنگ'],
    'Jhelum': ['جہلم', 'ضلع جہلم', 'jehlum'],
    'Kasur': ['قصور', 'ضلع قصور', 'qasoor', 'qasur'],
    'Khanewal': ['خانیوال', 'ضلع خانیوال', 'khane wal'],
    'Khushab': ['خوشاب', 'ضلع خوشاب'],
    'Lahore': ['لاہور', 'ضلع لاہور', 'lhr'],
    'Leiah': ['لیہ', 'لیا', 'لہیہ', 'ضلع لیہ', 'layyah', 'layya', 'leiah', 'liah', 'lia'],
    'Lodhran': ['لودھراں', 'ضلع لودھراں'],
    'Mandi Bahauddin': ['منڈی بہاؤالدین', 'منڈی بہاؤ الدین', 'mandi bahauddin', 'mandi baha ud din', 'mb din'],
    'Mianwali': ['میانوالی', 'ضلع میانوالی'],
    'Multan': ['ملتان', 'ضلع ملتان'],
    'Muzaffargarh': ['مظفر گڑھ', 'مظفرگڑھ', 'ضلع مظفر گڑھ', 'muzaffar garh', 'muzaffargarh', 'muzafargarh', 'کوٹ ادو', 'علی پور', 'جتوئی'],
    'Nankana Sahib': ['ننکانہ صاحب', 'ننکانہ', 'nankana sahib', 'nankana'],
    'Narowal': ['نارووال', 'ضلع نارووال', 'naro wal'],
    'Okara': ['اوکاڑہ', 'اوکاڑا', 'ضلع اوکاڑہ'],
    'Pakpattan': ['پاکپتن', 'پاک پتن', 'pak pattan', 'pakpattan'],
    'Rahim Yar Khan': ['رحیم یار خان', 'آر وائی خان', 'rahim yar khan', 'rahimyarkhan', 'ry khan', 'r.y. khan', 'rykhan'],
    'Rajanpur': ['راجن پور', 'راجنپور', 'فاضل پور', 'روجھان', 'جام پور', 'rajan pur', 'rajanpur', 'fazilpur', 'rojhan', 'jampur'],
    'Rawalpindi': ['راولپنڈی', 'راول پنڈی', 'پنڈی', 'rawalpindi', 'rawal pindi', 'pindi'],
    'Sahiwal': ['ساہیوال', 'ضلع ساہیوال', 'منٹگمری'],
    'Sargodha': ['سرگودھا', 'ضلع سرگودھا'],
    'Sheikhupura': ['شیخوپورہ', 'شیخوپورا', 'ضلع شیخوپورہ', 'sheikhupura', 'sheikhoopura'],
    'Sialkot': ['سیالکوٹ', 'ضلع سیالکوٹ'],
    'Toba Tek Singh': ['ٹوبہ ٹیک سنگھ', 'ٹوبہ', 'toba tek singh', 'toba', 'tts'],
    'Vehari': ['وہاڑی', 'ضلع وہاڑی', 'vihari'],

    # Sindh
    'Badin': ['بدین', 'ضلع بدین', 'ماتلی', 'گولارچی', 'تلہار', 'baadin', 'badin'],
    'Central Karachi': ['کراچی وسطی', 'وسطی کراچی', 'کراچی سنٹرل'],
    'Dadu': ['دادو', 'ڈاڈو', 'جوہی', 'میہڑ', 'خیرپور ناتھن شاہ', 'daadu', 'dadoo', 'dadu', 'johi', 'mehar', 'kn shah'],
    'East Karachi': ['کراچی شرقی', 'شرقی کراچی', 'کراچی ایسٹ'],
    'Ghotki': ['گھوٹکی', 'ضلع گھوٹکی', 'ڈہرکی', 'میرپور ماتھیلو', 'اوباڑو', 'ghotki', 'ghoki', 'daharki', 'mirpur mathelo', 'ubauro'],
    'Hyderabad': ['حیدرآباد', 'حیدر اباد', 'hyderabad', 'hyder abad'],
    'Jacobabad': ['جیکب آباد', 'جیکب اباد', 'جیکبہ', 'جیکبہ بابات', 'ٹھل', 'گڑھی خیرو', 'jacobabad', 'jakobabad', 'jacob abad', 'jakob abad', 'jikba', 'jikba babat', 'thul'],
    'Jamshoro': ['جامشورو', 'جام شورو', 'کوٹری', 'سیہون', 'کوٹری بیراج', 'jamshuro', 'jam shoro', 'jamshoro', 'kotri', 'sehwan', 'kotri barrage'],
    'Kambar Shahdad Kot': ['قمبر شہداد کوٹ', 'قمبر', 'شہداد کوٹ', 'قمبر شہدادکوٹ', 'qambar shahdadkot', 'kamber shahdadkot', 'shahdadkot', 'qambar', 'kambar'],
    'Kashmore': ['کشمور', 'قشمور', 'کندھ کوٹ', 'kashmore', 'kashmor', 'qashmore', 'kandhkot'],
    'Khairpur': ['خیرپور', 'خیر پور', 'گمبٹ', 'کوٹ ڈیجی', 'سوبھوڈیرو', 'khairpur', 'khairpoor', 'khairpur mirs', 'gambit', 'kot diji'],
    'Korangi Karachi': ['کورنگی', 'کراچی کورنگی', 'korangi'],
    'Larkana': ['لاڑکانہ', 'لاڑکانو', 'ضلع لاڑکانہ', 'larkana', 'larkano'],
    'Malir Karachi': ['ملیر', 'کراچی ملیر', 'malir'],
    'Matiari': ['مٹیاری', 'ضلع مٹیاری', 'matiari', 'matiyari', 'hala', 'ہالہ'],
    'Mirpur Khas': ['میرپور خاص', 'میر پور خاص', 'میرپورخاص', 'ڈگری', 'کوٹ غلام محمد', 'نوکوٹ', 'mirpur khas', 'mirpurkhas', 'mir pur khas', 'digri', 'naukot'],
    'Naushahro Feroze': ['نوشہرو فیروز', 'نوشہروفیروز', 'مورو', 'کنڈیارو', 'naushahro feroze', 'naushahroferoze', 'naushero feroze', 'nawabshah feroze', 'moro', 'kandiaro'],
    'Sanghar': ['سانگھڑ', 'ضلع سانگھڑ', 'شہدادپور', 'ٹنڈو آدم', 'سنجھورو', 'کھپرو', 'sanghar', 'sangher', 'shahdadpur', 'tando adam', 'khipro'],
    'Shaheed Benazir Abad': ['شہید بینظیر آباد', 'شہید بے نظیر آباد', 'نواب شاہ', 'نوابشاہ', 'بینظیر آباد', 'shaheed benazir abad', 'shaheed benazirabad', 'benazirabad', 'nawabshah', 'nawab shah'],
    'Shikarpur': ['شکارپور', 'ضلع شکارپور', 'shikarpur', 'shikaarpur'],
    'South Karachi': ['کراچی جنوبی', 'جنوبی کراچی', 'کراچی ساؤتھ', 'کراچی', 'karachi', 'khi'],
    'Sujawal': ['سجاول', 'ضلع سجاول', 'میرپور بٹھورو', 'شاہ بندر', 'sujawal', 'sujaawal', 'jati', 'shah bandar'],
    'Sukkur': ['سکھر', 'سخر', 'سکر', 'روہڑی', 'پنو عاقل', 'سکھر بیراج', 'sukkur', 'sakkhar', 'sukker', 'sukhar', 'sukhur', 'rohri', 'pano aqil'],
    'Tando Allahyar': ['ٹنڈو الہ یار', 'ٹنڈو اللہ یار', 'ٹنڈوالہ یار', 'tando allahyar', 'tando allah yaar'],
    'Tando Muhammad Khan': ['ٹنڈو محمد خان', 'ٹنڈو محمدخان', 'tando muhammad khan', 'tmkhan'],
    'Tharparkar': ['تھرپارکر', 'تھر پارکر', 'تھر', 'مٹھی', 'اسلام کوٹ', 'نگر پارکر', 'ڈپلو', 'چھانچھرو', 'tharparkar', 'tharparker', 'thar parkar', 'thar', 'mithi', 'islamkot', 'nagarparkar', 'diplo'],
    'Thatta': ['ٹھٹھہ', 'ٹھٹہ', 'گھارو', 'میرپور ساکرو', 'کیٹی بندر', 'thatta', 'thata', 'gharo', 'keti bandar'],
    'Umer Kot': ['عمرکوٹ', 'عمر کوٹ', 'سامارو', 'umer kot', 'umarkot', 'umerkot'],
    'West Karachi': ['کراچی غربی', 'غربی کراچی', 'کراچی ویسٹ'],

    # Balochistan
    'Awaran': ['آواران', 'اواران', 'ضلع آواران', 'awaran'],
    'Barkhan': ['بارکھان', 'ضلع بارکھان', 'barkhan'],
    'Chagai': ['چاغی', 'ضلع چاغی', 'دالبندین', 'chagai', 'dalbandin'],
    'Chaman': ['چمن', 'ضلع چمن', 'chaman'],
    'Dera Bugti': ['ڈیرہ بگٹی', 'سوئی', 'dera bugti', 'derabugti', 'sui'],
    'Duki': ['دوکی', 'ڈکی', 'ضلع دوکی', 'duki'],
    'Gwadar': ['گوادر', 'ضلع گوادر', 'پسنی', 'اورماڑہ', 'gwadar', 'pasni', 'ormara'],
    'Harnai': ['ہرنائی', 'ضلع ہرنائی', 'harnai'],
    'Jaffarabad': ['جعفر آباد', 'جعفرآباد', 'اوستہ محمد', 'ڈیرہ اللہ یار', 'jaffarabad', 'jafarabad', 'jaffar abad', 'usta muhammad', 'dera allah yar'],
    'Jhal Magsi': ['جھل مگسی', 'جھلمگسی', 'گنداوہ', 'jhal magsi', 'jhalmagsi', 'jhal magsee', 'gandawa'],
    'Kachhi': ['کچھی', 'بولان', 'ڈھادر', 'kachhi', 'bolan', 'dhadar'],
    'Kalat': ['قلات', 'ضلع قلات', 'kalat', 'kalaat', 'qalat'],
    'Kech': ['کیچ', 'تربت', 'kech', 'turbat'],
    'Kharan': ['خاران', 'ضلع خاران', 'kharan'],
    'Khuzdar': ['خضدار', 'ضلع خضدار', 'نال', 'khuzdar', 'khozdaar'],
    'Killa Abdullah': ['قلعہ عبداللہ', 'قلعہ عبد اللہ', 'killa abdullah', 'qila abdullah'],
    'Killa Saifullah': ['قلعہ سیف اللہ', 'قلعہ سیفاللہ', 'مسلم باغ', 'killa saifullah', 'qila saifullah', 'kila saifullah', 'muslim bagh'],
    'Kohlu': ['کوہلو', 'ضلع کوہلو', 'kohlu'],
    'Lasbela': ['لسبیلہ', 'لس بیلہ', 'حب', 'اوٹھل', 'بیلہ', 'وندر', 'lasbela', 'las bela', 'hub', 'uthal', 'bela', 'winder'],
    'Lehri': ['لہڑی', 'ضلع لہڑی', 'lehri'],
    'Loralai': ['لورالائی', 'ضلع لورالائی', 'بوستان', 'loralai'],
    'Mastung': ['مستونگ', 'ضلع مستونگ', 'mastung'],
    'Musakhel': ['موسیٰ خیل', 'موسی خیل', 'ضلع موسی خیل', 'musakhel', 'musa khel'],
    'Nasirabad': ['نصیر آباد', 'نصیرآباد', 'ڈیرہ مراد جمالی', 'nasirabad', 'naseerabad', 'nasir abad', 'dera murad jamali'],
    'Nushki': ['نوشکی', 'ضلع نوشکی', 'nushki'],
    'Panjgur': ['پنجگور', 'ضلع پنجگور', 'panjgur'],
    'Pishin': ['پشین', 'ضلع پشین', 'pishin'],
    'Quetta': ['کوئٹہ', 'ضلع کوئٹہ', 'quetta'],
    'Shaheed Sikandarabad': ['شہید سکندر آباد', 'سوراب', 'surab', 'shaheed sikandarabad'],
    'Sherani': ['شیرانی', 'ضلع شیرانی', 'sherani'],
    'Sibi': ['سبی', 'ضلع سبی', 'sibi', 'sibbi'],
    'Sohbatpur': ['صحبت پور', 'صحبتپور', 'ضلع صحبت پور', 'sohbatpur', 'sohbat pur'],
    'Washuk': ['واشک', 'ضلع واشک', 'بیسیمہ', 'washuk'],
    'Zhob': ['ژوب', 'ضلع ژوب', 'zhob'],
    'Ziarat': ['زیارت', 'ضلع زیارت', 'ziarat'],

    # Khyber Pakhtunkhwa
    'Abbottabad': ['ایبٹ آباد', 'ایبٹ اباد', 'ضلع ایبٹ آباد', 'حویلیاں', 'abbottabad', 'havelian'],
    'Bajaur': ['باجوڑ', 'ضلع باجوڑ', 'خار', 'bajaur', 'khar'],
    'Bannu': ['بنوں', 'ضلع بنوں', 'bannu'],
    'Batagram': ['بٹگرام', 'ضلع بٹگرام', 'batagram', 'battagram'],
    'Buner': ['بونیر', 'ضلع بونیر', 'ڈگر', 'buner', 'daggar'],
    'Charsadda': ['چارسدہ', 'ضلع چارسدہ', 'تنگی', 'شبقدر', 'charsadda', 'charsada', 'shabqadar'],
    'Chitral Lower': ['چترال', 'لوئر چترال', 'چترال زیریں', 'ضلع چترال', 'lower chitral', 'chitral'],
    'Chitral Upper': ['اپر چترال', 'چترال بالا', 'بونی', 'upper chitral', 'booni'],
    'D. I. Khan': ['ڈی آئی خان', 'ڈیرہ اسماعیل خان', 'پہاڑ پور', 'kulachi', 'd. i. khan', 'd.i khan', 'dikhan', 'd i khan', 'dera ismail khan'],
    'Hangu': ['ہنگو', 'ضلع ہنگو', 'ٹل', 'hangu', 'thal'],
    'Haripur': ['ہری پور', 'ہریپور', 'ضلع ہری پور', 'haripur', 'hari pur'],
    'Karak': ['کرک', 'ضلع کرک', 'تخت نصرتی', 'karak'],
    'Khyber': ['خیبر', 'ضلع خیبر', 'لنڈی کوتل', 'باڑہ', 'khyber', 'landi kotal', 'bara'],
    'Kohat': ['کوہاٹ', 'ضلع کوہاٹ', 'لاچی', 'kohat', 'lachi'],
    'Kohistan Lower': ['لوئر کوہستان', 'کوہستان زیریں', 'پتن', 'lower kohistan'],
    'Kohistan Upper': ['اپر کوہستان', 'کوہستان بالا', 'داسو', 'upper kohistan', 'dasu'],
    'Kolai Palas Kohistan': ['کولئی پالس', 'کولئی پالس کوہستان', 'kolai palas'],
    'Kurram': ['کرم', 'ضلع کرم', 'پاراچنار', 'صدہ', 'kurram', 'parachinar', 'sadda'],
    'Lakki Marwat': ['لکی مروت', 'ضلع لکی مروت', 'سرائے نورنگ', 'lakki marwat', 'serai naurang'],
    'Lower Dir': ['لوئر دیر', 'دیر زیریں', 'دیر', 'تیمرگرہ', 'lower dir', 'dir lower', 'timergara', 'dir'],
    'Malakand': ['مالاکنڈ', 'ملاکنڈ', 'بٹ خیلہ', 'درگئی', 'malakand', 'batkhela', 'dargai'],
    'Mansehra': ['مانسہرہ', 'ضلع مانسہرہ', 'بالاکوٹ', 'اوگی', 'mansehra', 'balakot', 'ogi'],
    'Mardan': ['مردان', 'ضلع مردان', 'تخت بھائی', 'کاٹلنگ', 'mardan', 'takht bhai'],
    'Mohmand': ['مہمند', 'ضلع مہمند', 'غلنئی', 'mohmand', 'ghallanai'],
    'North Waziristan': ['شمالی وزیرستان', 'میران شاہ', 'میر علی', 'north waziristan', 'miran shah', 'mir ali'],
    'Nowshera': ['نوشہرہ', 'ضلع نوشہرہ', 'پبی', 'رسالپور', 'nowshera', 'nowshehra', 'pabbi', 'risalpur'],
    'Orakzai': ['اورکزئی', 'ضلع اورکزئی', 'کلایہ', 'orakzai', 'kalaya'],
    'Peshawar': ['پشاور', 'ضلع پشاور', 'peshawar', 'pesh'],
    'Shangla': ['شانگلہ', 'ضلع شانگلہ', 'الپوری', 'بشام', 'shangla', 'alpuri', 'besham'],
    'South Waziristan': ['جنوبی وزیرستان', 'وانا', 'جنڈولہ', 'south waziristan', 'wana', 'waziristan'],
    'Swabi': ['صوابی', 'ضلع صوابی', 'ٹوپی', 'swabi', 'topi'],
    'Swat': ['سوات', 'ضلع سوات', 'مینگورہ', 'مدین', 'بحرین', 'کبل', 'خواrecognised', 'swat', 'swaat', 'mingora', 'madyan', 'bahrain', 'kabal'],
    'Tank': ['ٹانک', 'ضلع ٹانک', 'tank', 'taank'],
    'Tor Ghar': ['تور غر', 'تورغر', 'کالا ڈھاکہ', 'tor ghar', 'torghar', 'kala dhaka'],
    'Upper Dir': ['اپر دیر', 'دیر بالا', 'شرینگل', 'upper dir', 'dir upper', 'sharingal'],

    # Azad Kashmir
    'Bagh': ['باغ', 'ضلع باغ', 'دھیرکوٹ', 'bagh', 'dhir kot'],
    'Bhimber': ['بھمبر', 'ضلع بھمبر', 'برنالہ', 'سماہنی', 'bhimber', 'barnala', 'samahni'],
    'Haveli': ['حویلی', 'ضلع حویلی', 'کہوٹہ', 'haveli'],
    'Jhelum Valley': ['جہلم ویلی', 'ہٹیاں بالا', 'لیپہ', 'jhelum valley', 'hattian', 'leepa'],
    'Kotli': ['کوٹلی', 'ضلع کوٹلی', 'سہنسہ', 'خوئی رٹہ', 'kotli', 'sehnsa'],
    'Mirpur': ['میرپور', 'ضلع میرپور', 'ڈڈیال', 'mirpur astore', 'dadyal'],
    'Muzaffarabad': ['مظفر آباد', 'مظفرآباد', 'ضلع مظفر آباد', 'muzaffarabad', 'muzaffar abad'],
    'Neelum': ['نیلم', 'وادی نیلم', 'شاردا', 'آٹھمقام', 'neelum', 'neelum valley', 'sharda', 'athmuqam'],
    'Poonch': ['پونچھ', 'راولاکوٹ', 'راولا کوٹ', 'عباس پور', 'ہجیرہ', 'poonch', 'rawalakot', 'rawala kot', 'hajira'],
    'Sudhnoti': ['سدھنوتی', 'پلندری', 'بلوچ', 'sudhnoti', 'pallandri'],

    # Gilgit Baltistan
    'Astore': ['استور', 'ضلع استور', 'عید گاہ', 'astore'],
    'Darel': ['داریل', 'ضلع داریل', 'darel'],
    'Diamir': ['دیامر', 'ضلع دیامر', 'چلاس', 'diamir', 'chilas'],
    'Ghanche': ['گانچھے', 'خپلو', 'ghanche', 'khaplu'],
    'Ghizer': ['غذر', 'ضلع غذر', 'گاہکوچ', 'ghizer', 'gahkuch'],
    'Gilgit': ['گلگت', 'ضلع گلگت', 'جگلوٹ', 'gilgit', 'juglot'],
    'Gupis-Yasin': ['گوپس یاسین', 'یاسین', 'gupis yasin', 'gupis-yasin', 'yasin'],
    'Hunza': ['ہنزہ', 'علی آباد', 'کریم آباد', 'hunza', 'aliabad', 'karimabad'],
    'Kharmang': ['کھرمنگ', 'ٹولتی', 'kharmang', 'tolti'],
    'Nagar': ['نگر', 'ضلع نگر', 'سکندر آباد', 'nagar'],
    'Rondu': ['روندو', 'ضلع روندو', 'rondu'],
    'Shigar': ['شگر', 'ضلع شگر', 'shigar'],
    'Skardu': ['سکردو', 'ضلع سکردو', 'skardu'],
    'Tangir': ['تانگیر', 'ضلع تانگیر', 'tangir'],

    # Islamabad
    'Islamabad': ['اسلام آباد', 'اسلام اباد', 'اسلاماباد', 'islamabad', 'isloo', 'isb']
}

for dist, var_list in URDU_MAP.items():
    if dist not in valid_districts:
        print(f'WARNING: {dist} is NOT a valid gazetteer district!')
        continue
    for var in var_list:
        v = var.strip().lower()
        aliases[v] = dist

# Save back to aliases.json
with open(DATA_DIR / 'aliases.json', 'w', encoding='utf-8') as f:
    json.dump(aliases, f, ensure_ascii=False, indent=2)

print(f'Successfully built comprehensive aliases.json with {len(aliases)} total entries!')
