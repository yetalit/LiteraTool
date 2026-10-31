# LiteraTool

Development of A Software Tool for Literature Analysis and Visualization.

> **Citing this work?** See [Citation](#citation).

---

## Get it running

### Option A: Download the Windows app (easiest)

1. Go to the [Releases page](../../releases) and download `LiteraTool-windows.7z`.
2. Unzip it (7-Zip or similar).
3. Run `LiteraTool.exe` inside the `LiteraTool` folder.

> The release is **built automatically by GitHub Actions** from the tagged source code (see [`release.yml`](.github/workflows/release.yml)). No manual builds, no hidden changes: what you download is what's in the repo at that tag.
> Windows may show a SmartScreen warning because the exe isn't code-signed. Choose "More info" -> "Run anyway", or run from source (Option B).

### Option B: Run from source (Windows, macOS, Linux)

Requires Python 3.12 (other recent versions will most likely work).

```bash
git clone https://github.com/yetalit/LiteraTool.git
cd LiteraTool
pip install -r requirements.txt
cd src
python app.py
```

> Run it from inside `src/`. The app looks for its theme and image files in `src/_internal/`.

---

## Using it

1. Click **LOAD** (or drag and drop your file onto the window). Excel (`.xlsx`) and CSV (`.csv`) files both work.
2. *(Optional)* Click **YEAR GROUPS** to define the time periods used in the plots. Enter the start year of each group; the last group ends at the latest year in your data.
3. Click **PLOTS** to explore the pages (Year Dist., Sankey, Cat. Links, Author-Cat., Co-Authorship). Use **Filter Categories** to select which categories are included in a plot.
4. Click **Summary Table** to export an Excel summary.

---

## Prepare your data (read this, it matters)

Your literature review file must follow these rules:

**1. Two mandatory columns: year and author**
- Name them exactly `year` and `author` (also accepted: `authors`, `author(s)`).
- These labels must not appear anywhere else in the sheet.

**2. Separate multiple authors with `&`**
```
Jeff W.T. Kan & Zafer Bilda & John S. Gero
```
- Names are used exactly as written. LiteraTool does **not** merge spelling variants, initials, or alternate forms ("J. Gero" and "John S. Gero" count as two different people). Clean your names first.

**3. Category columns come after year and author**
- The software treats everything to the right of the **last** `year` / `author(s)` column as categories.

**4. One column = one category, named with its full path**
- Join the main category and its sub-categories with an underscore ( `_` ): `MachineLearning_DeepLearning_CNN`

**5. Filled cell = yes, empty cell = no**
- Any content in a category cell means the article belongs to that category. Leave it empty otherwise.

### Example

| year | author | ML_SupervisedLearning_DecisionTree | ML_UnsupervisedLearning_KMeans | ML_DeepLearning_CNN | ML_DeepLearning_Transformer |
|------|--------|:---:|:---:|:---:|:---:|
| 2019 | Jeff W.T. Kan & Zafer Bilda | x | | x | |
| 2021 | John S. Gero | | x | | x |

---

## License

Licensed under the **GNU GPL v3.0**. See [`LICENSE`](LICENSE).

## Acknowledgements

- **SankeyFlow** by [Riley Xu](https://github.com/riley-x/SankeyFlow) (BSD 2-Clause License). Our `sankeyflow.py` is a **modified version** of this library.
- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/), [Matplotlib](https://matplotlib.org/), [NumPy](https://numpy.org/), [pandas](https://pandas.pydata.org/), and [openpyxl](https://openpyxl.readthedocs.io/).

## Citation

```
@software{A_LiteraTool_2026,
  author  = {A, B and C, D},
  title   = {{LiteraTool}},
  version = {0.1.0},
  year    = {2026},
  doi     = {x},
  license = {GPL-3.0-only}
}
```

## Feedback

Found a bug or have a feature idea? [Open an issue](../../issues).
