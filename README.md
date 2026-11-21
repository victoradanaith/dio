# Dio learning tracker

A small tool for tracking a primary-school child's learning, built on the [Marble Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy): 1,900+ micro-topics with a prerequisite graph. On top of it, this project adds:

- `tracker/extensions.json`: Thai and Mandarin Pinyin topics in the same format as Marble's (Marble doesn't cover these subjects)
- `tracker/ssis-map.json`: school units (Singapore curriculum, P1) mapped onto taxonomy topics
- `tracker/dio.py`: CLI to log progress and generate two pages:
  - `dashboard.html`: per-subject log, foundations to check, topics ready next
  - `graph.html`: 3D graph of every topic (height = age, lines = prerequisites), coloured by the child's status, with "likely passed" inferred from prerequisites. Click a dot to see every foundation it needs.

```bash
python3 tracker/dio.py seed      # set every mapped topic to 'introduced'
python3 tracker/dio.py log ca1-ma-ch2 practising --note "Chapter test 18/20"
python3 tracker/dio.py next      # foundations to check / ready next
python3 tracker/dio.py build     # write dashboard.html + graph.html
```

The child's progress data (`tracker/progress.json`) and the generated pages are personal, so they're kept out of the repo.

## License
- Taxonomy data in `tracker/taxonomy/`: © Marble, [CC BY-SA 4.0](tracker/taxonomy/LICENSE-CONTENT). Source commit is in `tracker/taxonomy/SOURCE.txt`.
- `extensions.json` and `ssis-map.json` are adaptations of that data, so they're also CC BY-SA 4.0.
