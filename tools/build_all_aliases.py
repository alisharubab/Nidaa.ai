# Build comprehensive aliases mapping for all Pakistan districts, tehsils, and Urdu variants.
# Supports both:
#  1. Default (Admin-2 District Centroid Target) - safe for baseline core geocoding
#  2. --tehsil-targets (Admin-3 Sub-district Precision) - for pinpoint town accuracy
import argparse
import csv
import json
from pathlib import Path
import re
import sys
import unicodedata

DATA_DIR = Path('data')

def _normalize(s):
    if not s: return ''
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    return re.sub(r'\s+', ' ', s)

def build_aliases(tehsil_precision=False):
    with open(DATA_DIR / 'pak_gazetteer.csv', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    valid_districts = set(r['adm2_name'].strip() for r in rows)
    valid_tehsils = set(r['adm3_name'].strip() for r in rows)

    # Base dictionary
    aliases = {}

    # 1. Add all tehsils from gazetteer
    for r in rows:
        tehsil = r['adm3_name'].strip()
        district = r['adm2_name'].strip()
        k = tehsil.lower()
        target = tehsil if tehsil_precision else district
        if k != target.lower():
            aliases[k] = target

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
        'Muzaffargarh': ['مظفر گڑھ', 'مظفرگڑھ', 'ضلع مظفر گڑھ', 'muzaffar garh', 'muzaffargarh', 'muzafargarh'],
        'Nankana Sahib': ['ننکانہ صاحب', 'ننکانہ', 'nankana sahib', 'nankana'],
        'Narowal': ['نارووال', 'ضلع نارووال', 'naro wal'],
        'Okara': ['اوکاڑہ', 'اوکاڑا', 'ضلع اوکاڑہ'],
        'Pakpattan': ['پاکپتن', 'پاک پتن', 'pak pattan', 'pakpattan'],
        'Rahim Yar Khan': ['رحیم یار خان', 'آر وائی خان', 'rahim yar khan', 'rahimyarkhan', 'ry khan', 'r.y. khan', 'rykhan'],
        'Rajanpur': ['راجن پور', 'راجنپور', 'rajan pur', 'rajanpur'],
        'Rawalpindi': ['راولپنڈی', 'راول پنڈی', 'پنڈی', 'rawalpindi', 'rawal pindi', 'pindi'],
        'Sahiwal': ['ساہیوال', 'ضلع ساہیوال', 'منٹگمری'],
        'Sargodha': ['سرگودھا', 'ضلع سرگودھا'],
        'Sheikhupura': ['شیخوپورہ', 'شیخوپورا', 'ضلع شیخوپورہ', 'sheikhupura', 'sheikhoopura'],
        'Sialkot': ['سیالکوٹ', 'ضلع سیالکوٹ'],
        'Toba Tek Singh': ['ٹوبہ ٹیک سنگھ', 'ٹوبہ', 'toba tek singh', 'toba', 'tts'],
        'Vehari': ['وہاڑی', 'ضلع وہاڑی', 'vihari'],

        # Sindh
        'Badin': ['بدین', 'ضلع بدین', 'baadin', 'badin'],
        'Central Karachi': ['کراچی وسطی', 'وسطی کراچی', 'کراچی سنٹرل'],
        'Dadu': ['دادو', 'ڈاڈو', 'daadu', 'dadoo', 'dadu'],
        'East Karachi': ['کراچی شرقی', 'شرقی کراچی', 'کراچی ایسٹ'],
        'Ghotki': ['گھوٹکی', 'ضلع گھوٹکی', 'ghotki', 'ghoki'],
        'Hyderabad': ['حیدرآباد', 'حیدر اباد', 'hyderabad', 'hyder abad'],
        'Jacobabad': ['جیکب آباد', 'جیکب اباد', 'جیکبہ', 'جیکبہ بابات', 'jacobabad', 'jakobabad', 'jacob abad', 'jikba', 'jikba babat'],
        'Jamshoro': ['جامشورو', 'جام شورو', 'jamshuro', 'jam shoro', 'jamshoro'],
        'Kambar Shahdad Kot': ['قمبر شہداد کوٹ', 'قمبر', 'شہداد کوٹ', 'قمبر شہدادکوٹ', 'qambar shahdadkot', 'kamber shahdadkot', 'shahdadkot', 'qambar', 'kambar'],
        'Kashmore': ['کشمور', 'قشمور', 'kashmore', 'kashmor', 'qashmore'],
        'Khairpur': ['خیرپور', 'خیر پور', 'khairpur', 'khairpoor', 'khairpur mirs'],
        'Korangi Karachi': ['کورنگی', 'کراچی کورنگی', 'korangi'],
        'Larkana': ['لاڑکانہ', 'لاڑکانو', 'ضلع لاڑکانہ', 'larkana', 'larkano'],
        'Malir Karachi': ['ملیر', 'کراچی ملیر', 'malir'],
        'Matiari': ['مٹیاری', 'ضلع مٹیاری', 'matiari', 'matiyari'],
        'Mirpur Khas': ['میرپور خاص', 'میر پور خاص', 'میرپورخاص', 'mirpur khas', 'mirpurkhas', 'mir pur khas'],
        'Naushahro Feroze': ['نوشہرو فیروز', 'نوشہروفیروز', 'naushahro feroze', 'naushahroferoze', 'naushero feroze', 'nawabshah feroze'],
        'Sanghar': ['سانگھڑ', 'ضلع سانگھڑ', 'sanghar', 'sangher'],
        'Shaheed Benazir Abad': ['شہید بینظیر آباد', 'شہید بے نظیر آباد', 'نواب شاہ', 'نوابشاہ', 'بینظیر آباد', 'shaheed benazir abad', 'shaheed benazirabad', 'benazirabad', 'nawabshah', 'nawab shah'],
        'Shikarpur': ['شکارپور', 'ضلع شکارپور', 'shikarpur', 'shikaarpur'],
        'South Karachi': ['کراچی جنوبی', 'جنوبی کراچی', 'کراچی ساؤتھ', 'کراچی', 'karachi', 'khi'],
        'Sujawal': ['سجاول', 'ضلع سجاول', 'sujawal', 'sujaawal'],
        'Sukkur': ['سکھر', 'سخر', 'سکر', 'سکھر بیراج', 'sukkur', 'sakkhar', 'sukker', 'sukhar', 'sukhur'],
        'Tando Allahyar': ['ٹنڈو الہ یار', 'ٹنڈو اللہ یار', 'ٹنڈوالہ یار', 'tando allahyar', 'tando allah yaar'],
        'Tando Muhammad Khan': ['ٹنڈو محمد خان', 'ٹنڈو محمدخان', 'tando muhammad khan', 'tmkhan'],
        'Tharparkar': ['تھرپارکر', 'تھر پارکر', 'تھر', 'tharparkar', 'tharparker', 'thar parkar', 'thar'],
        'Thatta': ['ٹھٹھہ', 'ٹھٹہ', 'thatta', 'thata'],
        'Umer Kot': ['عمرکوٹ', 'عمر کوٹ', 'umer kot', 'umarkot', 'umerkot'],
        'West Karachi': ['کراچی غربی', 'غربی کراچی', 'کراچی ویسٹ'],

        # Balochistan
        'Awaran': ['آواران', 'اواران', 'ضلع آواران', 'awaran'],
        'Barkhan': ['بارکھان', 'ضلع بارکھان', 'barkhan'],
        'Chagai': ['چاغی', 'ضلع چاغی', 'chagai'],
        'Chaman': ['چمن', 'ضلع چمن', 'chaman'],
        'Dera Bugti': ['ڈیرہ بگٹی', 'dera bugti', 'derabugti'],
        'Duki': ['دوکی', 'ڈکی', 'ضلع دوکی', 'duki'],
        'Gwadar': ['گوادر', 'ضلع گوادر', 'gwadar'],
        'Harnai': ['ہرنائی', 'ضلع ہرنائی', 'harnai'],
        'Jaffarabad': ['جعفر آباد', 'جعفرآباد', 'jaffarabad', 'jafarabad', 'jaffar abad'],
        'Jhal Magsi': ['جھل مگسی', 'جھلمگسی', 'jhal magsi', 'jhalmagsi', 'jhal magsee'],
        'Kachhi': ['کچھی', 'بولان', 'kachhi', 'bolan'],
        'Kalat': ['قلات', 'ضلع قلات', 'kalat', 'kalaat', 'qalat'],
        'Kech': ['کیچ', 'تربت', 'kech', 'turbat'],
        'Kharan': ['خاران', 'ضلع خاران', 'kharan'],
        'Khuzdar': ['خضدار', 'ضلع خضدار', 'khuzdar', 'khozdaar'],
        'Killa Abdullah': ['قلعہ عبداللہ', 'قلعہ عبد اللہ', 'killa abdullah', 'qila abdullah'],
        'Killa Saifullah': ['قلعہ سیف اللہ', 'قلعہ سیفاللہ', 'killa saifullah', 'qila saifullah', 'kila saifullah'],
        'Kohlu': ['کوہلو', 'ضلع کوہلو', 'kohlu'],
        'Lasbela': ['لسبیلہ', 'لس بیلہ', 'lasbela', 'las bela'],
        'Lehri': ['لہڑی', 'ضلع لہڑی', 'lehri'],
        'Loralai': ['لورالائی', 'ضلع لورالائی', 'loralai'],
        'Mastung': ['مستونگ', 'ضلع مستونگ', 'mastung'],
        'Musakhel': ['موسیٰ خیل', 'موسی خیل', 'ضلع موسی خیل', 'musakhel', 'musa khel'],
        'Nasirabad': ['نصیر آباد', 'نصیرآباد', 'nasirabad', 'naseerabad', 'nasir abad'],
        'Nushki': ['نوشکی', 'ضلع نوشکی', 'nushki'],
        'Panjgur': ['پنجگور', 'ضلع پنجگور', 'panjgur'],
        'Pishin': ['پشین', 'ضلع پشین', 'pishin'],
        'Quetta': ['کوئٹہ', 'ضلع کوئٹہ', 'quetta'],
        'Shaheed Sikandarabad': ['شہید سکندر آباد', 'سوراب', 'surab', 'shaheed sikandarabad'],
        'Sherani': ['شیرانی', 'ضلع شیرانی', 'sherani'],
        'Sibi': ['سبی', 'ضلع سبی', 'sibi', 'sibbi'],
        'Sohbatpur': ['صحبت پور', 'صحبتپور', 'ضلع صحبت پور', 'sohbatpur', 'sohbat pur'],
        'Washuk': ['واشک', 'ضلع واشک', 'washuk'],
        'Zhob': ['ژوب', 'ضلع ژوب', 'zhob'],
        'Ziarat': ['زیارت', 'ضلع زیارت', 'ziarat'],

        # Khyber Pakhtunkhwa
        'Abbottabad': ['ایبٹ آباد', 'ایبٹ اباد', 'ضلع ایبٹ آباد', 'abbottabad'],
        'Bajaur': ['باجوڑ', 'ضلع باجوڑ', 'bajaur'],
        'Bannu': ['بنوں', 'ضلع بنوں', 'bannu'],
        'Batagram': ['بٹگرام', 'ضلع بٹگرام', 'batagram', 'battagram'],
        'Buner': ['بونیر', 'ضلع بونیر', 'buner'],
        'Charsadda': ['چارسدہ', 'ضلع چارسدہ', 'charsadda', 'charsada'],
        'Chitral Lower': ['چترال', 'لوئر چترال', 'چترال زیریں', 'ضلع چترال', 'lower chitral', 'chitral'],
        'Chitral Upper': ['اپر چترال', 'چترال بالا', 'upper chitral'],
        'D. I. Khan': ['ڈی آئی خان', 'ڈیرہ اسماعیل خان', 'd. i. khan', 'd.i khan', 'dikhan', 'd i khan', 'dera ismail khan'],
        'Hangu': ['ہنگو', 'ضلع ہنگو', 'hangu'],
        'Haripur': ['ہری پور', 'ہریپور', 'ضلع ہری پور', 'haripur', 'hari pur'],
        'Karak': ['کرک', 'ضلع کرک', 'karak'],
        'Khyber': ['خیبر', 'ضلع خیبر', 'khyber'],
        'Kohat': ['کوہاٹ', 'ضلع کوہاٹ', 'kohat'],
        'Kohistan Lower': ['لوئر کوہستان', 'کوہستان زیریں', 'lower kohistan'],
        'Kohistan Upper': ['اپر کوہستان', 'کوہستان بالا', 'upper kohistan'],
        'Kolai Palas Kohistan': ['کولئی پالس', 'کولئی پالس کوہستان', 'kolai palas'],
        'Kurram': ['کرم', 'ضلع کرم', 'kurram'],
        'Lakki Marwat': ['لکی مروت', 'ضلع لکی مروت', 'lakki marwat'],
        'Lower Dir': ['لوئر دیر', 'دیر زیریں', 'دیر', 'lower dir', 'dir lower', 'dir'],
        'Malakand': ['مالاکنڈ', 'ملاکنڈ', 'malakand'],
        'Mansehra': ['مانسہرہ', 'ضلع مانسہرہ', 'mansehra'],
        'Mardan': ['مردان', 'ضلع مردان', 'mardan'],
        'Mohmand': ['مہمند', 'ضلع مہمند', 'mohmand'],
        'North Waziristan': ['شمالی وزیرستان', 'north waziristan'],
        'Nowshera': ['نوشہرہ', 'ضلع نوشہرہ', 'nowshera', 'nowshehra'],
        'Orakzai': ['اورکزئی', 'ضلع اورکزئی', 'orakzai'],
        'Peshawar': ['پشاور', 'ضلع پشاور', 'peshawar', 'pesh'],
        'Shangla': ['شانگلہ', 'ضلع شانگلہ', 'shangla'],
        'South Waziristan': ['جنوبی وزیرستان', 'south waziristan', 'waziristan'],
        'Swabi': ['صوابی', 'ضلع صوابی', 'swabi'],
        'Swat': ['سوات', 'ضلع سوات', 'swat', 'swaat'],
        'Tank': ['ٹانک', 'ضلع ٹانک', 'tank', 'taank'],
        'Tor Ghar': ['تور غر', 'تورغر', 'کالا ڈھاکہ', 'tor ghar', 'torghar', 'kala dhaka'],
        'Upper Dir': ['اپر دیر', 'دیر بالا', 'upper dir', 'dir upper'],

        # Azad Kashmir
        'Bagh': ['باغ', 'ضلع باغ', 'bagh'],
        'Bhimber': ['بھمبر', 'ضلع بھمبر', 'bhimber'],
        'Haveli': ['حویلی', 'ضلع حویلی', 'haveli'],
        'Jhelum Valley': ['جہلم ویلی', 'jhelum valley'],
        'Kotli': ['کوٹلی', 'ضلع کوٹلی', 'kotli'],
        'Mirpur': ['میرپور', 'ضلع میرپور', 'mirpur'],
        'Muzaffarabad': ['مظفر آباد', 'مظفرآباد', 'ضلع مظفر آباد', 'muzaffarabad', 'muzaffar abad'],
        'Neelum': ['نیلم', 'وادی نیلم', 'neelum', 'neelum valley'],
        'Poonch': ['پونچھ', 'راولاکوٹ', 'راولا کوٹ', 'poonch', 'rawalakot'],
        'Sudhnoti': ['سدھنوتی', 'پلندری', 'sudhnoti', 'pallandri'],

        # Gilgit Baltistan
        'Astore': ['استور', 'ضلع استور', 'astore'],
        'Darel': ['داریل', 'ضلع داریل', 'darel'],
        'Diamir': ['دیامر', 'ضلع دیامر', 'diamir'],
        'Ghanche': ['گانچھے', 'ghanche'],
        'Ghizer': ['غذر', 'ضلع غذر', 'ghizer'],
        'Gilgit': ['گلگت', 'ضلع گلگت', 'gilgit'],
        'Gupis-Yasin': ['گوپس یاسین', 'gupis yasin', 'gupis-yasin'],
        'Hunza': ['ہنزہ', 'hunza'],
        'Kharmang': ['کھرمنگ', 'kharmang'],
        'Nagar': ['نگر', 'ضلع نگر', 'nagar'],
        'Rondu': ['روندو', 'ضلع روندو', 'rondu'],
        'Shigar': ['شگر', 'ضلع شگر', 'shigar'],
        'Skardu': ['سکردو', 'ضلع سکردو', 'skardu'],
        'Tangir': ['تانگیر', 'ضلع تانگیر', 'tangir'],

        # Islamabad
        'Islamabad': ['اسلام آباد', 'اسلام اباد', 'اسلاماباد', 'islamabad', 'isloo', 'isb']
    }

    # 3. Tehsils / Sub-districts explicit mapping
    TEHSIL_MAP = {
        'Mian Channu': ['میاں چنوں', 'میاں چنو', 'mian channu', 'mianchannu'],
        'Kabirwala': ['کبیروالا', 'کبیر والا', 'kabirwala'],
        'Jahanian': ['جہانیاں', 'jahanian'],
        'Johi': ['جوہی', 'johi'],
        'Mehar': ['میہڑ', 'mehar'],
        'Khairpur Nathan Shah': ['خیرپور ناتھن شاہ', 'kn shah'],
        'Rohri': ['روہڑی', 'rohri'],
        'Pano Aqil': ['پنو عاقل', 'pano aqil'],
        'Kotri': ['کوٹری', 'کوٹری بیراج', 'kotri'],
        'Sehwan': ['سیہون', 'sehwan'],
        'Hub': ['حب', 'hub'],
        'Bela': ['بیلہ', 'bela'],
        'Uthal': ['اوٹھل', 'uthal'],
        'Winder': ['وندر', 'winder'],
        'Sui': ['سوئی', 'sui'],
        'Taunsa': ['تونسہ', 'taunsa'],
        'Fazilpur': ['فاضل پور', 'fazilpur'],
        'Rojhan': ['روجھان', 'rojhan'],
        'Jampur': ['جام پور', 'jampur'],
        'Mithi': ['مٹھی', 'mithi'],
        'Islamkot': ['اسلام کوٹ', 'islamkot'],
        'Nagarparkar': ['نگر پارکر', 'nagarparkar'],
        'Diplo': ['ڈپلو', 'diplo'],
        'Thul': ['ٹھل', 'thul'],
        'Garhi Khairo': ['گڑھی خیرو', 'garhi khairo'],
        'Kandhkot': ['کندھ کوٹ', 'kandhkot'],
        'Kot Addu': ['کوٹ ادو', 'kot addu'],
        'Alipur': ['علی پور', 'alipur'],
        'Jatoi': ['جتوئی', 'jatoi'],
        'Daharki': ['ڈہرکی', 'daharki'],
        'Mirpur Mathelo': ['میرپور ماتھیلو', 'mirpur mathelo'],
        'Ubauro': ['اوباڑو', 'ubauro'],
        'Moro': ['مورو', 'moro'],
        'Kandiaro': ['کنڈیارو', 'kandiaro'],
        'Shahdadpur': ['شہدادپور', 'shahdadpur'],
        'Tando Adam': ['ٹنڈو آدم', 'tando adam'],
        'Khipro': ['کھپرو', 'khipro'],
        'Matli': ['ماتلی', 'matli'],
        'Gharo': ['گھارو', 'gharo'],
        'Keti Bandar': ['کیٹی بندر', 'keti bandar'],
        'Usta Muhammad': ['اوستہ محمد', 'usta muhammad'],
        'Dera Allah Yar': ['ڈیرہ اللہ یار', 'dera allah yar'],
        'Dera Murad Jamali': ['ڈیرہ مراد جمالی', 'dera murad jamali'],
        'Turbat': ['تربت', 'turbat'],
        'Pasni': ['پسنی', 'pasni'],
        'Ormara': ['اورماڑہ', 'ormara'],
        'Chilas': ['چلاس', 'chilas'],
        'Parachinar': ['پاراچنار', 'parachinar'],
        'Balakot': ['بالاکوٹ', 'balakot'],
        'Timergara': ['تیمرگرہ', 'timergara'],
        'Mingora': ['مینگورہ', 'mingora'],
    }

    # Map districts
    for dist, var_list in URDU_MAP.items():
        if dist not in valid_districts: continue
        for var in var_list:
            aliases[var.strip().lower()] = dist

    # Map tehsils: if tehsil_precision is True, map to Tehsil; else map to parent District
    tehsil_to_district = {r['adm3_name'].strip(): r['adm2_name'].strip() for r in rows}
    for teh, var_list in TEHSIL_MAP.items():
        target = teh if tehsil_precision else tehsil_to_district.get(teh, teh)
        for var in var_list:
            aliases[var.strip().lower()] = target

    # Add normalized keys so NFKD Unicode decomposition never misses
    final_aliases = {}
    for k, v in aliases.items():
        final_aliases[k] = v
        nk = _normalize(k)
        if nk:
            final_aliases[nk] = v

    return final_aliases

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tehsils', action='store_true', help='Set alias targets to specific tehsils (requires updated geocode.py)')
    args = parser.parse_args()

    mode_name = 'Tehsil Sub-district Precision' if args.tehsils else 'District Centroid (Default)'
    print(f'Building aliases in mode: {mode_name}')
    data = build_aliases(tehsil_precision=args.tehsils)

    with open(DATA_DIR / 'aliases.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Successfully wrote {len(data)} aliases to data/aliases.json!')
