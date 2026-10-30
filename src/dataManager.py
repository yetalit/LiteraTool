import numpy as np
import pandas as pd


class manager:
    def __init__(self):
        self.DF = None

    def open(self, file_path):
        prevDF = self.DF
        if file_path.endswith('.csv'):
            self.DF = pd.read_csv(file_path)
        elif file_path.endswith('.xlsx'):
            self.DF = pd.read_excel(file_path)
        else:
            self.DF = None
        if self.DF is not None:
            self.DF = self.DF.loc[:, ~self.DF.columns.str.contains('^Unnamed:')]
            self.DF.columns = self.DF.columns.str.lower()
            self.DF.columns = self.DF.columns.str.strip()
            self.DF = self.DF.loc[:, self.DF.columns.notna() & (self.DF.columns.astype(str) != '')]
            try:
                self.DF['year'] = pd.to_numeric(self.DF['year'])
            except:
                self.DF = prevDF
                return 'There is a problem with year column!'
            author_col = 'author(s)'
            if author_col not in self.DF.columns:
                author_col = 'authors'
                if author_col not in self.DF.columns:
                    author_col = 'author'
            self.author = author_col
            try:
                authors_stripped = self.DF[author_col].str.strip()
                if (self.DF[author_col].isna() | authors_stripped.eq('') | authors_stripped.str.endswith('&')).any():
                    raise Exception
                self.categories_start = max(self.DF.columns.get_loc('year'), self.DF.columns.get_loc(author_col)) + 1
                categories = [self.DF.columns[i].split('_')[0] for i in range(self.categories_start, self.DF.shape[1])]
                self.categories = []
                for i in range(len(categories)):
                    if categories[i] not in self.categories:
                        self.categories.append(categories[i])
            except:
                self.DF = prevDF
                return 'There is a problem with authors column!'

            min_year = int(self.DF['year'].min())
            max_year = int(self.DF['year'].max())

            start_year = int(np.floor(min_year / 10) * 10)
            end_year = int(np.ceil((max_year + 1) / 10) * 10)

            # Default: 10-year intervals
            intervals = [10] * ((end_year - start_year) // 10)

            self.bins = [start_year]
            for length in intervals:
                self.bins.append(self.bins[-1] + length)

            self.year_labels = [
                f'{max(start, min_year)}-{min(end - 1, max_year)}'
                for start, end in zip(self.bins[:-1], self.bins[1:])
            ]

            self.set_year_groups()

            return ''
        self.DF = prevDF
        return 'Failed to load the dataset!'

    def set_year_groups(self):
        self.year_groups = pd.cut(
            self.DF['year'],
            bins=self.bins,
            right=False,
            labels=self.year_labels
        )

    def analyze(self, idg, *filters):
        if self.DF is not None:
            if idg == 1:
                df = self.DF.sort_values(by='year')
                start_year = df.loc[0, 'year']
                end_year = df.loc[df.shape[0] - 1, 'year']
                years = np.arange(start_year, end_year+1, 1, dtype=int).tolist()
                categories = [df.columns[i].split('_')[0] for i in range(self.categories_start, df.shape[1])]
                unique_columns = {}
                for i in range(len(categories)):
                    if categories[i] in unique_columns:
                        with pd.option_context("future.no_silent_downcasting", True):
                            unique_columns[categories[i]] = unique_columns[categories[i]].fillna(df.iloc[:, i + self.categories_start])
                    else:
                        unique_columns[categories[i]] = df.iloc[:, i + self.categories_start]
                unique_columns_keys = list(unique_columns.keys())
                year_counts_for_cats = np.zeros((len(unique_columns_keys), len(years)), dtype=int)
                for i in range(len(unique_columns_keys)):
                    year_counts = df[unique_columns[unique_columns_keys[i]].notna()]['year'].value_counts().to_dict()
                    for year in year_counts:
                        year_counts_for_cats[i, years.index(year)] = year_counts[year]
                return unique_columns_keys, years, year_counts_for_cats
            if idg == 2:
                df = self.DF.sort_values(by='year')
                year_groups = pd.cut(df['year'], bins=self.bins, right=False, labels=self.year_labels)
                year_group_counts = year_groups.value_counts().to_dict()
                nodes = [[('All', df.shape[0], df.shape[0])], []]
                flows = []
                sorted_keys = sorted(year_group_counts.keys(), key=lambda x: int(x.split('-')[0]))
                for key in sorted_keys:
                    nodes[1].append((key, 0, year_group_counts[key]))
                    flows.append(('All', key, year_group_counts[key]))

                category_arrays = [df.columns[i].split('_') for i in range(self.categories_start, df.shape[1])]
                categories = [category_arrays[i][0] for i in range(len(category_arrays))]
                unique_columns = {}
                for i in range(len(categories)):
                    if categories[i] in unique_columns:
                        with pd.option_context("future.no_silent_downcasting", True):
                            unique_columns[categories[i]] = unique_columns[categories[i]].fillna(
                                df.iloc[:, i + self.categories_start])
                    else:
                        unique_columns[categories[i]] = df.iloc[:, i + self.categories_start]
                unique_columns_keys = list(unique_columns.keys())
                nodes.append([])
                for i in range(len(unique_columns_keys)):
                    notna = unique_columns[unique_columns_keys[i]].notna()
                    notna_sum = notna.sum()
                    nodes[2].append((unique_columns_keys[i], 0, notna_sum))
                    _year_group = year_groups[notna]
                    _year_group_counts = _year_group.value_counts().to_dict()
                    for key in _year_group_counts:
                        flows.append((key, unique_columns_keys[i], _year_group_counts[key]))
                        for n in range(len(nodes[1])):
                            if nodes[1][n][0] == key:
                                nodes[1][n] = (key, nodes[1][n][1] + _year_group_counts[key], nodes[1][n][2])
                                break
                # For subs
                longest = len(max(category_arrays, key=len))
                for level in range(1, longest):
                    categories = []
                    for i in range(len(category_arrays)):
                        if level < len(category_arrays[i]):
                            categories.append(category_arrays[i][level])
                    _columns = {}
                    column_pointer = 0
                    unique_column_keys = []
                    for i in range(len(categories)):
                        if categories[i] not in unique_column_keys:
                            unique_column_keys.append(categories[i])
                        label = ''
                        for j in range(column_pointer, len(category_arrays)):
                            if ('_' + categories[i] + '_') in df.columns[j + self.categories_start] or df.columns[j + self.categories_start].endswith('_' + categories[i]):
                                column_pointer = j + 1
                                label = df.columns[j + self.categories_start].split('_')[level-1] + '_' + categories[i]
                                break
                        if label in _columns:
                            with pd.option_context("future.no_silent_downcasting", True):
                                _columns[label] = _columns[label].fillna(
                                    df.iloc[:, column_pointer - 1 + self.categories_start])
                        else:
                            _columns[label] = df.iloc[:, column_pointer - 1 + self.categories_start]
                    column_keys = list(_columns.keys())
                    nodes.append([])
                    for i in range(len(unique_column_keys)):
                        nodes[level + 2].append((unique_column_keys[i], 0, 0))
                    for i in range(len(column_keys)):
                        notna = _columns[column_keys[i]].notna()
                        notna_sum = notna.sum()
                        pa_ch = column_keys[i].split('_')
                        parent, child = pa_ch[0], pa_ch[1]
                        for n in range(len(nodes[level+2])):
                            if nodes[level+2][n][0] == child:
                                nodes[level+2][n] = (child, 0, nodes[level+2][n][2] + notna_sum)
                                break
                        for n in range(len(nodes[level+1])):
                            if nodes[level+1][n][0] == parent:
                                nodes[level+1][n] = (parent, nodes[level+1][n][1] + notna_sum, nodes[level+1][n][2])
                                break
                        flows.append((parent, child, notna_sum))

                return nodes, flows
            if idg == 3:
                categories = [self.DF.columns[i].split('_')[0] for i in range(self.categories_start, self.DF.shape[1])]
                links = [[] for _ in range(self.DF.shape[0])]
                for i in range(len(links)):
                    for j in range(self.categories_start, self.DF.shape[1]):
                        if not pd.isna(self.DF.iloc[i, j]) and categories[j - self.categories_start] not in links[i]:
                            links[i].append(categories[j - self.categories_start])

                return self.categories, links, self.year_groups.values.tolist()
            if idg == 4:
                df = self.DF.loc[self.year_groups == filters[0]]
                categories = [df.columns[i].split('_')[0] for i in range(self.categories_start, df.shape[1])]
                links = [[] for _ in range(df.shape[0])]
                for i in range(len(links)):
                    for j in range(self.categories_start, df.shape[1]):
                        if not pd.isna(df.iloc[i, j]) and categories[j - self.categories_start] not in links[i]:
                            links[i].append(categories[j - self.categories_start])
                unique_categories = []
                for i in range(len(categories)):
                    if categories[i] not in unique_categories:
                        unique_categories.append(categories[i])
                authors = df[self.author].str.strip().str.split('&').values.tolist()
                unique_authors = []
                unique_authors_lower = []
                for i in range(df.shape[0]):
                    for j in range(len(authors[i])):
                        authors[i][j] = authors[i][j].strip()
                        if authors[i][j] in unique_authors:
                            continue
                        authors_lower = authors[i][j].lower()
                        if authors_lower in unique_authors_lower:
                            authors[i][j] = unique_authors[unique_authors_lower.index(authors_lower)]
                        else:
                            unique_authors.append(authors[i][j])
                            unique_authors_lower.append(authors_lower)
                return unique_authors, authors, unique_categories, links
            if idg == 5:
                df = self.DF.loc[self.year_groups == filters[0]]
                authors = df[self.author].str.strip().str.split('&').values.tolist()
                unique_authors = []
                unique_authors_lower = []
                for i in range(df.shape[0]):
                    for j in range(len(authors[i])):
                        authors[i][j] = authors[i][j].strip()
                        if authors[i][j] in unique_authors:
                            continue
                        authors_lower = authors[i][j].lower()
                        if authors_lower in unique_authors_lower:
                            authors[i][j] = unique_authors[unique_authors_lower.index(authors_lower)]
                        else:
                            unique_authors.append(authors[i][j])
                            unique_authors_lower.append(authors_lower)
                return unique_authors, authors
        return None
