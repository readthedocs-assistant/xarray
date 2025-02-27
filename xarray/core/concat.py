from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Dict,
    Hashable,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
    overload,
)

import pandas as pd

from . import dtypes, utils
from .alignment import align
from .duck_array_ops import lazy_array_equiv
from .merge import _VALID_COMPAT, merge_attrs, unique_variable
from .variable import IndexVariable, Variable, as_variable
from .variable import concat as concat_vars

if TYPE_CHECKING:
    from .dataarray import DataArray
    from .dataset import Dataset

compat_options = Literal[
    "identical", "equals", "broadcast_equals", "no_conflicts", "override"
]
concat_options = Literal["all", "minimal", "different"]


@overload
def concat(
    objs: Iterable["Dataset"],
    dim: Hashable | "DataArray" | pd.Index,
    data_vars: concat_options | List[Hashable] = "all",
    coords: concat_options | List[Hashable] = "different",
    compat: compat_options = "equals",
    positions: Optional[Iterable[int]] = None,
    fill_value: object = dtypes.NA,
    join: str = "outer",
    combine_attrs: str = "override",
) -> "Dataset":
    ...


@overload
def concat(
    objs: Iterable["DataArray"],
    dim: Hashable | "DataArray" | pd.Index,
    data_vars: concat_options | List[Hashable] = "all",
    coords: concat_options | List[Hashable] = "different",
    compat: compat_options = "equals",
    positions: Optional[Iterable[int]] = None,
    fill_value: object = dtypes.NA,
    join: str = "outer",
    combine_attrs: str = "override",
) -> "DataArray":
    ...


def concat(
    objs,
    dim,
    data_vars="all",
    coords="different",
    compat="equals",
    positions=None,
    fill_value=dtypes.NA,
    join="outer",
    combine_attrs="override",
):
    """Concatenate xarray objects along a new or existing dimension.

    Parameters
    ----------
    objs : sequence of Dataset and DataArray
        xarray objects to concatenate together. Each object is expected to
        consist of variables and coordinates with matching shapes except for
        along the concatenated dimension.
    dim : Hashable or DataArray or pandas.Index
        Name of the dimension to concatenate along. This can either be a new
        dimension name, in which case it is added along axis=0, or an existing
        dimension name, in which case the location of the dimension is
        unchanged. If dimension is provided as a DataArray or Index, its name
        is used as the dimension to concatenate along and the values are added
        as a coordinate.
    data_vars : {"minimal", "different", "all"} or list of Hashable, optional
        These data variables will be concatenated together:
          * "minimal": Only data variables in which the dimension already
            appears are included.
          * "different": Data variables which are not equal (ignoring
            attributes) across all datasets are also concatenated (as well as
            all for which dimension already appears). Beware: this option may
            load the data payload of data variables into memory if they are not
            already loaded.
          * "all": All data variables will be concatenated.
          * list of dims: The listed data variables will be concatenated, in
            addition to the "minimal" data variables.

        If objects are DataArrays, data_vars must be "all".
    coords : {"minimal", "different", "all"} or list of Hashable, optional
        These coordinate variables will be concatenated together:
          * "minimal": Only coordinates in which the dimension already appears
            are included.
          * "different": Coordinates which are not equal (ignoring attributes)
            across all datasets are also concatenated (as well as all for which
            dimension already appears). Beware: this option may load the data
            payload of coordinate variables into memory if they are not already
            loaded.
          * "all": All coordinate variables will be concatenated, except
            those corresponding to other dimensions.
          * list of Hashable: The listed coordinate variables will be concatenated,
            in addition to the "minimal" coordinates.
    compat : {"identical", "equals", "broadcast_equals", "no_conflicts", "override"}, optional
        String indicating how to compare non-concatenated variables of the same name for
        potential conflicts. This is passed down to merge.

        - "broadcast_equals": all values must be equal when variables are
          broadcast against each other to ensure common dimensions.
        - "equals": all values and dimensions must be the same.
        - "identical": all values, dimensions and attributes must be the
          same.
        - "no_conflicts": only values which are not null in both datasets
          must be equal. The returned dataset then contains the combination
          of all non-null values.
        - "override": skip comparing and pick variable from first dataset
    positions : None or list of integer arrays, optional
        List of integer arrays which specifies the integer positions to which
        to assign each dataset along the concatenated dimension. If not
        supplied, objects are concatenated in the provided order.
    fill_value : scalar or dict-like, optional
        Value to use for newly missing values. If a dict-like, maps
        variable names to fill values. Use a data array's name to
        refer to its values.
    join : {"outer", "inner", "left", "right", "exact"}, optional
        String indicating how to combine differing indexes
        (excluding dim) in objects

        - "outer": use the union of object indexes
        - "inner": use the intersection of object indexes
        - "left": use indexes from the first object with each dimension
        - "right": use indexes from the last object with each dimension
        - "exact": instead of aligning, raise `ValueError` when indexes to be
          aligned are not equal
        - "override": if indexes are of same size, rewrite indexes to be
          those of the first object with that dimension. Indexes for the same
          dimension must have the same size in all objects.
    combine_attrs : {"drop", "identical", "no_conflicts", "drop_conflicts", \
                     "override"} or callable, default: "override"
        A callable or a string indicating how to combine attrs of the objects being
        merged:

        - "drop": empty attrs on returned Dataset.
        - "identical": all attrs must be the same on every object.
        - "no_conflicts": attrs from all objects are combined, any that have
          the same name must also have the same value.
        - "drop_conflicts": attrs from all objects are combined, any that have
          the same name but different values are dropped.
        - "override": skip comparing and copy attrs from the first dataset to
          the result.

        If a callable, it must expect a sequence of ``attrs`` dicts and a context object
        as its only parameters.

    Returns
    -------
    concatenated : type of objs

    See also
    --------
    merge

    Examples
    --------
    >>> da = xr.DataArray(
    ...     np.arange(6).reshape(2, 3), [("x", ["a", "b"]), ("y", [10, 20, 30])]
    ... )
    >>> da
    <xarray.DataArray (x: 2, y: 3)>
    array([[0, 1, 2],
           [3, 4, 5]])
    Coordinates:
      * x        (x) <U1 'a' 'b'
      * y        (y) int64 10 20 30

    >>> xr.concat([da.isel(y=slice(0, 1)), da.isel(y=slice(1, None))], dim="y")
    <xarray.DataArray (x: 2, y: 3)>
    array([[0, 1, 2],
           [3, 4, 5]])
    Coordinates:
      * x        (x) <U1 'a' 'b'
      * y        (y) int64 10 20 30

    >>> xr.concat([da.isel(x=0), da.isel(x=1)], "x")
    <xarray.DataArray (x: 2, y: 3)>
    array([[0, 1, 2],
           [3, 4, 5]])
    Coordinates:
      * x        (x) <U1 'a' 'b'
      * y        (y) int64 10 20 30

    >>> xr.concat([da.isel(x=0), da.isel(x=1)], "new_dim")
    <xarray.DataArray (new_dim: 2, y: 3)>
    array([[0, 1, 2],
           [3, 4, 5]])
    Coordinates:
        x        (new_dim) <U1 'a' 'b'
      * y        (y) int64 10 20 30
    Dimensions without coordinates: new_dim

    >>> xr.concat([da.isel(x=0), da.isel(x=1)], pd.Index([-90, -100], name="new_dim"))
    <xarray.DataArray (new_dim: 2, y: 3)>
    array([[0, 1, 2],
           [3, 4, 5]])
    Coordinates:
        x        (new_dim) <U1 'a' 'b'
      * y        (y) int64 10 20 30
      * new_dim  (new_dim) int64 -90 -100
    """
    # TODO: add ignore_index arguments copied from pandas.concat
    # TODO: support concatenating scalar coordinates even if the concatenated
    # dimension already exists
    from .dataarray import DataArray
    from .dataset import Dataset

    try:
        first_obj, objs = utils.peek_at(objs)
    except StopIteration:
        raise ValueError("must supply at least one object to concatenate")

    if compat not in _VALID_COMPAT:
        raise ValueError(
            f"compat={compat!r} invalid: must be 'broadcast_equals', 'equals', 'identical', 'no_conflicts' or 'override'"
        )

    if isinstance(first_obj, DataArray):
        f = _dataarray_concat
    elif isinstance(first_obj, Dataset):
        f = _dataset_concat
    else:
        raise TypeError(
            "can only concatenate xarray Dataset and DataArray "
            f"objects, got {type(first_obj)}"
        )
    return f(
        objs, dim, data_vars, coords, compat, positions, fill_value, join, combine_attrs
    )


def _calc_concat_dim_coord(dim):
    """
    Infer the dimension name and 1d coordinate variable (if appropriate)
    for concatenating along the new dimension.
    """
    from .dataarray import DataArray

    if isinstance(dim, str):
        coord = None
    elif not isinstance(dim, (DataArray, Variable)):
        dim_name = getattr(dim, "name", None)
        if dim_name is None:
            dim_name = "concat_dim"
        coord = IndexVariable(dim_name, dim)
        dim = dim_name
    elif not isinstance(dim, DataArray):
        coord = as_variable(dim).to_index_variable()
        (dim,) = coord.dims
    else:
        coord = dim
        if coord.name is None:
            coord.name = dim.dims[0]
        (dim,) = coord.dims
    return dim, coord


def _calc_concat_over(datasets, dim, dim_names, data_vars, coords, compat):
    """
    Determine which dataset variables need to be concatenated in the result,
    """
    # Return values
    concat_over = set()
    equals = {}

    if dim in dim_names:
        concat_over_existing_dim = True
        concat_over.add(dim)
    else:
        concat_over_existing_dim = False

    concat_dim_lengths = []
    for ds in datasets:
        if concat_over_existing_dim:
            if dim not in ds.dims:
                if dim in ds:
                    ds = ds.set_coords(dim)
        concat_over.update(k for k, v in ds.variables.items() if dim in v.dims)
        concat_dim_lengths.append(ds.dims.get(dim, 1))

    def process_subset_opt(opt, subset):
        if isinstance(opt, str):
            if opt == "different":
                if compat == "override":
                    raise ValueError(
                        f"Cannot specify both {subset}='different' and compat='override'."
                    )
                # all nonindexes that are not the same in each dataset
                for k in getattr(datasets[0], subset):
                    if k not in concat_over:
                        equals[k] = None

                        variables = [
                            ds.variables[k] for ds in datasets if k in ds.variables
                        ]

                        if len(variables) == 1:
                            # coords="different" doesn't make sense when only one object
                            # contains a particular variable.
                            break
                        elif len(variables) != len(datasets) and opt == "different":
                            raise ValueError(
                                f"{k!r} not present in all datasets and coords='different'. "
                                f"Either add {k!r} to datasets where it is missing or "
                                "specify coords='minimal'."
                            )

                        # first check without comparing values i.e. no computes
                        for var in variables[1:]:
                            equals[k] = getattr(variables[0], compat)(
                                var, equiv=lazy_array_equiv
                            )
                            if equals[k] is not True:
                                # exit early if we know these are not equal or that
                                # equality cannot be determined i.e. one or all of
                                # the variables wraps a numpy array
                                break

                        if equals[k] is False:
                            concat_over.add(k)

                        elif equals[k] is None:
                            # Compare the variable of all datasets vs. the one
                            # of the first dataset. Perform the minimum amount of
                            # loads in order to avoid multiple loads from disk
                            # while keeping the RAM footprint low.
                            v_lhs = datasets[0].variables[k].load()
                            # We'll need to know later on if variables are equal.
                            computed = []
                            for ds_rhs in datasets[1:]:
                                v_rhs = ds_rhs.variables[k].compute()
                                computed.append(v_rhs)
                                if not getattr(v_lhs, compat)(v_rhs):
                                    concat_over.add(k)
                                    equals[k] = False
                                    # computed variables are not to be re-computed
                                    # again in the future
                                    for ds, v in zip(datasets[1:], computed):
                                        ds.variables[k].data = v.data
                                    break
                            else:
                                equals[k] = True

            elif opt == "all":
                concat_over.update(
                    set(getattr(datasets[0], subset)) - set(datasets[0].dims)
                )
            elif opt == "minimal":
                pass
            else:
                raise ValueError(f"unexpected value for {subset}: {opt}")
        else:
            invalid_vars = [k for k in opt if k not in getattr(datasets[0], subset)]
            if invalid_vars:
                if subset == "coords":
                    raise ValueError(
                        "some variables in coords are not coordinates on "
                        f"the first dataset: {invalid_vars}"
                    )
                else:
                    raise ValueError(
                        "some variables in data_vars are not data variables "
                        f"on the first dataset: {invalid_vars}"
                    )
            concat_over.update(opt)

    process_subset_opt(data_vars, "data_vars")
    process_subset_opt(coords, "coords")
    return concat_over, equals, concat_dim_lengths


# determine dimensional coordinate names and a dict mapping name to DataArray
def _parse_datasets(
    datasets: Iterable["Dataset"],
) -> Tuple[Dict[Hashable, Variable], Dict[Hashable, int], Set[Hashable], Set[Hashable]]:

    dims: Set[Hashable] = set()
    all_coord_names: Set[Hashable] = set()
    data_vars: Set[Hashable] = set()  # list of data_vars
    dim_coords: Dict[Hashable, Variable] = {}  # maps dim name to variable
    dims_sizes: Dict[Hashable, int] = {}  # shared dimension sizes to expand variables

    for ds in datasets:
        dims_sizes.update(ds.dims)
        all_coord_names.update(ds.coords)
        data_vars.update(ds.data_vars)

        # preserves ordering of dimensions
        for dim in ds.dims:
            if dim in dims:
                continue

            if dim not in dim_coords:
                dim_coords[dim] = ds.coords[dim].variable
        dims = dims | set(ds.dims)

    return dim_coords, dims_sizes, all_coord_names, data_vars


def _dataset_concat(
    datasets: List["Dataset"],
    dim: Union[str, "DataArray", pd.Index],
    data_vars: Union[str, List[str]],
    coords: Union[str, List[str]],
    compat: str,
    positions: Optional[Iterable[int]],
    fill_value: object = dtypes.NA,
    join: str = "outer",
    combine_attrs: str = "override",
) -> "Dataset":
    """
    Concatenate a sequence of datasets along a new or existing dimension
    """
    from .dataset import Dataset

    datasets = list(datasets)

    if not all(isinstance(dataset, Dataset) for dataset in datasets):
        raise TypeError(
            "The elements in the input list need to be either all 'Dataset's or all 'DataArray's"
        )

    dim, coord = _calc_concat_dim_coord(dim)
    # Make sure we're working on a copy (we'll be loading variables)
    datasets = [ds.copy() for ds in datasets]
    datasets = list(
        align(*datasets, join=join, copy=False, exclude=[dim], fill_value=fill_value)
    )

    dim_coords, dims_sizes, coord_names, data_names = _parse_datasets(datasets)
    dim_names = set(dim_coords)
    unlabeled_dims = dim_names - coord_names

    both_data_and_coords = coord_names & data_names
    if both_data_and_coords:
        raise ValueError(
            f"{both_data_and_coords!r} is a coordinate in some datasets but not others."
        )
    # we don't want the concat dimension in the result dataset yet
    dim_coords.pop(dim, None)
    dims_sizes.pop(dim, None)

    # case where concat dimension is a coordinate or data_var but not a dimension
    if (dim in coord_names or dim in data_names) and dim not in dim_names:
        datasets = [ds.expand_dims(dim) for ds in datasets]

    # determine which variables to concatentate
    concat_over, equals, concat_dim_lengths = _calc_concat_over(
        datasets, dim, dim_names, data_vars, coords, compat
    )

    # determine which variables to merge, and then merge them according to compat
    variables_to_merge = (coord_names | data_names) - concat_over - dim_names

    result_vars = {}
    if variables_to_merge:
        to_merge: Dict[Hashable, List[Variable]] = {
            var: [] for var in variables_to_merge
        }

        for ds in datasets:
            for var in variables_to_merge:
                if var in ds:
                    to_merge[var].append(ds.variables[var])

        for var in variables_to_merge:
            result_vars[var] = unique_variable(
                var, to_merge[var], compat=compat, equals=equals.get(var, None)
            )
    else:
        result_vars = {}
    result_vars.update(dim_coords)

    # assign attrs and encoding from first dataset
    result_attrs = merge_attrs([ds.attrs for ds in datasets], combine_attrs)
    result_encoding = datasets[0].encoding

    # check that global attributes are fixed across all datasets if necessary
    for ds in datasets[1:]:
        if compat == "identical" and not utils.dict_equiv(ds.attrs, result_attrs):
            raise ValueError("Dataset global attributes not equal.")

    # we've already verified everything is consistent; now, calculate
    # shared dimension sizes so we can expand the necessary variables
    def ensure_common_dims(vars):
        # ensure each variable with the given name shares the same
        # dimensions and the same shape for all of them except along the
        # concat dimension
        common_dims = tuple(pd.unique([d for v in vars for d in v.dims]))
        if dim not in common_dims:
            common_dims = (dim,) + common_dims
        for var, dim_len in zip(vars, concat_dim_lengths):
            if var.dims != common_dims:
                common_shape = tuple(dims_sizes.get(d, dim_len) for d in common_dims)
                var = var.set_dims(common_dims, common_shape)
            yield var

    # stack up each variable to fill-out the dataset (in order)
    # n.b. this loop preserves variable order, needed for groupby.
    for k in datasets[0].variables:
        if k in concat_over:
            try:
                vars = ensure_common_dims([ds[k].variable for ds in datasets])
            except KeyError:
                raise ValueError(f"{k!r} is not present in all datasets.")
            combined = concat_vars(vars, dim, positions, combine_attrs=combine_attrs)
            assert isinstance(combined, Variable)
            result_vars[k] = combined
        elif k in result_vars:
            # preserves original variable order
            result_vars[k] = result_vars.pop(k)

    result = Dataset(result_vars, attrs=result_attrs)
    absent_coord_names = coord_names - set(result.variables)
    if absent_coord_names:
        raise ValueError(
            f"Variables {absent_coord_names!r} are coordinates in some datasets but not others."
        )
    result = result.set_coords(coord_names)
    result.encoding = result_encoding

    result = result.drop_vars(unlabeled_dims, errors="ignore")

    if coord is not None:
        # add concat dimension last to ensure that its in the final Dataset
        result[coord.name] = coord

    return result


def _dataarray_concat(
    arrays: Iterable["DataArray"],
    dim: Union[str, "DataArray", pd.Index],
    data_vars: Union[str, List[str]],
    coords: Union[str, List[str]],
    compat: str,
    positions: Optional[Iterable[int]],
    fill_value: object = dtypes.NA,
    join: str = "outer",
    combine_attrs: str = "override",
) -> "DataArray":
    from .dataarray import DataArray

    arrays = list(arrays)

    if not all(isinstance(array, DataArray) for array in arrays):
        raise TypeError(
            "The elements in the input list need to be either all 'Dataset's or all 'DataArray's"
        )

    if data_vars != "all":
        raise ValueError(
            "data_vars is not a valid argument when concatenating DataArray objects"
        )

    datasets = []
    for n, arr in enumerate(arrays):
        if n == 0:
            name = arr.name
        elif name != arr.name:
            if compat == "identical":
                raise ValueError("array names not identical")
            else:
                arr = arr.rename(name)
        datasets.append(arr._to_temp_dataset())

    ds = _dataset_concat(
        datasets,
        dim,
        data_vars,
        coords,
        compat,
        positions,
        fill_value=fill_value,
        join=join,
        combine_attrs=combine_attrs,
    )

    merged_attrs = merge_attrs([da.attrs for da in arrays], combine_attrs)

    result = arrays[0]._from_temp_dataset(ds, name)
    result.attrs = merged_attrs

    return result
