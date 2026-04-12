from django.db import migrations

LAGOS_AREAS = [
    # Lagos Island / Central
    "Lagos Island",
    "Victoria Island",
    "Ikoyi",
    "Lekki",
    "Ajah",
    "Epe",
    "Ibeju-Lekki",

    # Lagos Mainland
    "Surulere",
    "Yaba",
    "Ebute Metta",
    "Mushin",
    "Oshodi",
    "Isolo",
    "Ikeja",
    "Maryland",
    "Ojota",
    "Ketu",
    "Mile 12",
    "Ikorodu",
    "Kosofe",
    "Bariga",
    "Somolu",
    "Gbagada",
    "Oworonshoki",
    "Palmgrove",

    # Apapa / Wharf
    "Apapa",
    "Ajegunle",
    "Orile",

    # Festac / Amuwo-Odofin
    "Festac Town",
    "Amuwo-Odofin",
    "Mile 2",
    "Satellite Town",

    # Alimosho / Egbeda Axis
    "Alimosho",
    "Egbeda",
    "Idimu",
    "Ikotun",
    "Igando",
    "Ayobo",
    "Ipaja",

    # Agege / Ifako-Ijaiye
    "Agege",
    "Ifako-Ijaiye",
    "Ogba",
    "Fagba",
    "Mangoro",
    "Iju",

    # Ojo / Badagry Axis
    "Ojo",
    "Badagry",
    "Seme",

    # Berger / Ojodu
    "Ojodu Berger",
    "Magodo",
    "Isheri",
    "Omole",
    "Olowora",

    # Iyana Ipaja / Abule Egba
    "Iyana Ipaja",
    "Abule Egba",
    "Meiran",
    "Ekoro",
    "Agbado",

    # Other Notable Areas
    "Anthony Village",
    "Ogudu",
    "Oregun",
    "Alausa",
    "Mende",
    "Ilupeju",
    "Oke-Odo",
    "Pen Cinema",
    "Ijora",
    "Costain",
    "Lawanson",
    "Itire",
    "Ojuelegba",
]


def seed_areas(apps, schema_editor):
    Area = apps.get_model("common", "Area")
    Area.objects.bulk_create(
        [Area(name=name, state="Lagos") for name in LAGOS_AREAS],
        ignore_conflicts=True,
    )


def remove_areas(apps, schema_editor):
    Area = apps.get_model("common", "Area")
    Area.objects.filter(state="Lagos", name__in=LAGOS_AREAS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_areas, remove_areas),
    ]
