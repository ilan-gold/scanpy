import anndata as ad
import scanpy as sc
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
import pytest


@pytest.mark.parametrize(
    'data_key',
    ['layers', 'obsm', 'varm'],
)
@pytest.mark.parametrize(
    'groupby_df_key',
    [
        'obs',
        'var',
    ],
)
def test_groupby_different_data_locations(data_key, groupby_df_key):
    if (data_key == 'varm' and groupby_df_key == 'obs') or (
        data_key == 'obsm' and groupby_df_key == 'var'
    ):
        pytest.skip("invalid parameter combination")
    ax_base = ["A", "B"]
    ax_groupby = [
        "v0",
        "v1",
        "v2",
        "w0",
        "w1",
        "a1",
        "a2",
        "a3",
        "b1",
        "b2",
        "c1",
        "c2",
        "d0",
    ]

    df_groupby = pd.DataFrame(index=pd.Index(ax_groupby, name="cell"))
    df_groupby["key"] = pd.Categorical([c[0] for c in ax_groupby])
    df_groupby["key_superset"] = pd.Categorical([c[0] for c in ax_groupby]).map(
        {'v': 'v', 'w': 'v', 'a': 'a', 'b': 'a', 'c': 'a', 'd': 'a'}
    )
    df_groupby["key_subset"] = pd.Categorical([c[1] for c in ax_groupby])
    df_groupby["weight"] = 2.0

    df_base = pd.DataFrame(index=ax_base)

    X = np.array(
        [
            [0, -2],
            [1, 13],
            [2, 1],  # v
            [3, 12],
            [4, 2],  # w
            [5, 11],
            [6, 3],
            [7, 10],  # a
            [8, 4],
            [9, 9],  # b
            [10, 5],
            [11, 8],  # c
            [12, 6],  # d
        ],
        dtype=np.float32,
    )
    data_dense = X
    if groupby_df_key == 'obs':
        data_sparse_mat_dict = {data_key: {'test': csr_matrix(X)}}
        adata_sparse = ad.AnnData(
            **{'obs': df_groupby, 'var': df_base, **data_sparse_mat_dict}
        )
        data_dense_mat_dict = {data_key: {'test': X}}
        adata_dense = ad.AnnData(
            **{'obs': df_groupby, 'var': df_base, **data_dense_mat_dict}
        )
    else:
        if data_key != 'varm':
            data_dense = X.T
        data_sparse_mat_dict = {data_key: {'test': csr_matrix(data_dense)}}
        adata_sparse = ad.AnnData(
            **{'obs': df_base, 'var': df_groupby, **data_sparse_mat_dict}
        )
        data_dense_mat_dict = {data_key: {'test': data_dense}}
        adata_dense = ad.AnnData(
            **{'obs': df_base, 'var': df_groupby, **data_dense_mat_dict}
        )

    data_dict = {(data_key if data_key != 'layers' else 'layer'): 'test'}
    stats_sparse = sc.get.aggregated(
        adata=adata_sparse,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
        **data_dict,
    )
    stats_dense = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
        **data_dict,
    )

    # superset columns can be kept but not subsets
    assert 'key_superset' in getattr(stats_sparse, groupby_df_key)
    assert 'key_subset' not in getattr(stats_sparse, groupby_df_key)

    assert np.allclose(
        getattr(stats_sparse, groupby_df_key)['count'],
        getattr(stats_sparse, groupby_df_key)['count'],
    )
    assert np.allclose(
        getattr(stats_sparse, data_key)['mean'], getattr(stats_dense, data_key)['mean']
    )
    assert np.allclose(
        getattr(stats_sparse, data_key)['var'],
        getattr(stats_dense, data_key)['var'],
        equal_nan=True,
    )

    stats_weight = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
        weight="weight",
        **data_dict,
    )
    sum_ = sc.get.aggregated(
        adata=adata_sparse, by="key", df_key=groupby_df_key, how='sum', **data_dict
    )
    sum_weight = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='sum',
        weight="weight",
        **data_dict,
    )

    def get_single_agg(adata, key, agg):
        if key == 'obsm' or key == 'varm':
            return getattr(adata, key)[agg]
        return adata.X

    assert np.allclose(
        2 * get_single_agg(sum_, data_key, 'sum'),
        get_single_agg(sum_weight, data_key, 'sum'),
    )
    assert np.allclose(
        getattr(stats_sparse, data_key)['mean'], getattr(stats_weight, data_key)['mean']
    )
    assert np.allclose(
        getattr(stats_sparse, data_key)['var'],
        getattr(stats_dense, data_key)['var'],
        equal_nan=True,
    )

    key_set = ["v", "w"]
    mean_key_set_adata = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='mean',
        key_set=key_set,
        **data_dict,
    )
    subset_idx = getattr(stats_sparse, groupby_df_key).index.isin(key_set)
    subset_adata = (
        stats_sparse[subset_idx, :]
        if groupby_df_key == 'obs'
        else stats_sparse[:, subset_idx]
    )
    subset_mean = getattr(subset_adata, data_key)['mean']
    key_set_mean = get_single_agg(mean_key_set_adata, data_key, 'mean')
    assert np.allclose(subset_mean, key_set_mean)

    df = pd.DataFrame(
        index=getattr(adata_dense, groupby_df_key)["key"],
        columns=getattr(
            adata_dense, f"{'var' if groupby_df_key == 'obs' else 'obs'}_names"
        ),
        data=data_dense.T
        if groupby_df_key == 'var' and data_key != 'varm'
        else data_dense,
    )
    grouped_agg_df = (
        df.groupby('key')
        .agg(["count", "mean", "var"])
        .swaplevel(axis=1)
        .sort_index(axis=1)
    )
    mean = getattr(stats_dense, data_key)['mean']
    if groupby_df_key == 'var' and data_key != 'varm':
        mean = mean.T
    assert np.allclose(mean, grouped_agg_df['mean'].values)
    var = getattr(stats_dense, data_key)['var']
    if groupby_df_key == 'var' and data_key != 'varm':
        var = var.T
    assert np.allclose(var, grouped_agg_df['var'].values, equal_nan=True)
    assert np.allclose(
        getattr(stats_dense, groupby_df_key)['count'],
        grouped_agg_df['count']['A'].values,
    )  # returns for both columns but counts only needs one because it is the same


@pytest.mark.parametrize(
    'groupby_df_key',
    [
        'obs',
        'var',
    ],
)
def test_groupby_X(groupby_df_key):
    ax_base = ["A", "B"]
    ax_groupby = [
        "v0",
        "v1",
        "v2",
        "w0",
        "w1",
        "a1",
        "a2",
        "a3",
        "b1",
        "b2",
        "c1",
        "c2",
        "d0",
    ]

    df_groupby = pd.DataFrame(index=pd.Index(ax_groupby, name="cell"))
    df_groupby["key"] = pd.Categorical([c[0] for c in ax_groupby])
    df_groupby["key_superset"] = pd.Categorical([c[0] for c in ax_groupby]).map(
        {'v': 'v', 'w': 'v', 'a': 'a', 'b': 'a', 'c': 'a', 'd': 'a'}
    )
    df_groupby["key_subset"] = pd.Categorical([c[1] for c in ax_groupby])
    df_groupby["weight"] = 2.0

    df_base = pd.DataFrame(index=ax_base)

    X = np.array(
        [
            [0, -2],
            [1, 13],
            [2, 1],  # v
            [3, 12],
            [4, 2],  # w
            [5, 11],
            [6, 3],
            [7, 10],  # a
            [8, 4],
            [9, 9],  # b
            [10, 5],
            [11, 8],  # c
            [12, 6],  # d
        ],
        dtype=np.float32,
    )
    data_dense = X
    if groupby_df_key == 'obs':
        adata_sparse = ad.AnnData(obs=df_groupby, var=df_base, X=csr_matrix(X))
        adata_dense = ad.AnnData(obs=df_groupby, var=df_base, X=X)
    else:
        adata_sparse = ad.AnnData(obs=df_base, var=df_groupby, X=data_dense.T)
        adata_dense = ad.AnnData(obs=df_base, var=df_groupby, X=csr_matrix(X).T)

    stats_sparse = sc.get.aggregated(
        adata=adata_sparse,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
    )
    stats_dense = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
    )

    # superset columns can be kept but not subsets
    assert 'key_superset' in getattr(stats_sparse, groupby_df_key)
    assert 'key_subset' not in getattr(stats_sparse, groupby_df_key)

    assert np.allclose(
        getattr(stats_sparse, groupby_df_key)['count'],
        getattr(stats_sparse, groupby_df_key)['count'],
    )
    assert np.allclose(stats_sparse.layers['mean'], stats_dense.layers['mean'])
    assert np.allclose(stats_sparse.layers['var'], stats_dense.layers['var'], equal_nan=True)

    stats_weight = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='count_mean_var',
        weight="weight",
    )
    sum_ = sc.get.aggregated(
        adata=adata_sparse, by="key", df_key=groupby_df_key, how='sum'
    )
    sum_weight = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='sum',
        weight="weight",
    )

    assert np.allclose(2 * sum_.X, sum_weight.X)
    assert np.allclose(stats_sparse.layers['mean'], stats_weight.layers['mean'])
    assert np.allclose(
        stats_sparse.layers['var'], stats_dense.layers['var'], equal_nan=True
    )

    key_set = ["v", "w"]
    mean_key_set_adata = sc.get.aggregated(
        adata=adata_dense,
        by="key",
        df_key=groupby_df_key,
        how='mean',
        key_set=key_set,
    )
    subset_idx = getattr(stats_sparse, groupby_df_key).index.isin(key_set)
    subset_adata = (
        stats_sparse[subset_idx, :]
        if groupby_df_key == 'obs'
        else stats_sparse[:, subset_idx]
    )
    subset_mean = subset_adata.layers['mean']
    key_set_mean = mean_key_set_adata.X
    assert np.allclose(subset_mean, key_set_mean)

    df = pd.DataFrame(
        index=getattr(adata_dense, groupby_df_key)["key"],
        columns=getattr(
            adata_dense, f"{'var' if groupby_df_key == 'obs' else 'obs'}_names"
        ),
        data=data_dense
    )
    grouped_agg_df = (
        df.groupby('key')
        .agg(["count", "mean", "var"])
        .swaplevel(axis=1)
        .sort_index(axis=1)
    )
    mean = stats_dense.layers['mean']
    if groupby_df_key == 'var':
        mean = mean.T
    assert np.allclose(mean, grouped_agg_df['mean'].values)
    var = stats_dense.layers['var']
    if groupby_df_key == 'var':
        var = var.T
    assert np.allclose(var, grouped_agg_df['var'].values, equal_nan=True)
    assert np.allclose(
        getattr(stats_dense, groupby_df_key)['count'],
        grouped_agg_df['count']['A'].values,
    )  # returns for both columns but counts only needs one because it is the same
