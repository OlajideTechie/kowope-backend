from django.db import migrations

AREA_LGA_MAP = {
    # Lagos Island / Central
    "Lagos Island": "Lagos Island",
    "Victoria Island": "Eti-Osa",
    "Ikoyi": "Eti-Osa",
    "Lekki": "Eti-Osa",
    "Ajah": "Eti-Osa",
    "Epe": "Epe",
    "Ibeju-Lekki": "Ibeju-Lekki",

    # Lagos Mainland
    "Surulere": "Surulere",
    "Yaba": "Lagos Mainland",
    "Ebute Metta": "Lagos Mainland",
    "Mushin": "Mushin",
    "Oshodi": "Oshodi-Isolo",
    "Isolo": "Oshodi-Isolo",
    "Ikeja": "Ikeja",
    "Maryland": "Ikeja",
    "Ojota": "Kosofe",
    "Ketu": "Kosofe",
    "Mile 12": "Kosofe",
    "Ikorodu": "Ikorodu",
    "Kosofe": "Kosofe",
    "Bariga": "Shomolu",
    "Somolu": "Shomolu",
    "Gbagada": "Kosofe",
    "Oworonshoki": "Kosofe",
    "Palmgrove": "Shomolu",

    # Apapa / Wharf
    "Apapa": "Apapa",
    "Ajegunle": "Ajeromi-Ifelodun",
    "Orile": "Lagos Mainland",

    # Festac / Amuwo-Odofin
    "Festac Town": "Amuwo-Odofin",
    "Amuwo-Odofin": "Amuwo-Odofin",
    "Mile 2": "Amuwo-Odofin",
    "Satellite Town": "Amuwo-Odofin",

    # Alimosho / Egbeda Axis
    "Alimosho": "Alimosho",
    "Egbeda": "Alimosho",
    "Idimu": "Alimosho",
    "Ikotun": "Alimosho",
    "Igando": "Alimosho",
    "Ayobo": "Alimosho",
    "Ipaja": "Alimosho",

    # Agege / Ifako-Ijaiye
    "Agege": "Agege",
    "Ifako-Ijaiye": "Ifako-Ijaiye",
    "Ogba": "Ifako-Ijaiye",
    "Fagba": "Ifako-Ijaiye",
    "Mangoro": "Agege",
    "Iju": "Ifako-Ijaiye",

    # Ojo / Badagry Axis
    "Ojo": "Ojo",
    "Badagry": "Badagry",
    "Seme": "Badagry",

    # Berger / Ojodu
    "Ojodu Berger": "Kosofe",
    "Magodo": "Kosofe",
    "Isheri": "Kosofe",
    "Omole": "Kosofe",
    "Olowora": "Kosofe",

    # Iyana Ipaja / Abule Egba
    "Iyana Ipaja": "Alimosho",
    "Abule Egba": "Agege",
    "Meiran": "Agege",
    "Ekoro": "Agege",
    "Agbado": "Ifako-Ijaiye",

    # Other Notable Areas
    "Anthony Village": "Kosofe",
    "Ogudu": "Kosofe",
    "Oregun": "Ikeja",
    "Alausa": "Ikeja",
    "Mende": "Ikeja",
    "Ilupeju": "Mushin",
    "Oke-Odo": "Alimosho",
    "Pen Cinema": "Agege",
    "Ijora": "Lagos Mainland",
    "Costain": "Lagos Mainland",
    "Lawanson": "Surulere",
    "Itire": "Surulere",
    "Ojuelegba": "Surulere",
}


def seed_lgas(apps, schema_editor):
    Area = apps.get_model("common", "Area")
    for name, lga in AREA_LGA_MAP.items():
        Area.objects.filter(name=name).update(lga=lga)


def reverse_lgas(apps, schema_editor):
    Area = apps.get_model("common", "Area")
    Area.objects.filter(name__in=AREA_LGA_MAP.keys()).update(lga="")


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0003_area_lga"),
    ]

    operations = [
        migrations.RunPython(seed_lgas, reverse_lgas),
    ]
