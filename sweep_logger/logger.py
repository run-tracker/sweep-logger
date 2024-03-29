import abc
import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, List, NamedTuple, Optional

import run_logger
from gql import gql


class ParamChoice(NamedTuple):
    key: str
    choice: Iterable


class SweepMethod(Enum):
    grid = auto()
    random = auto()


class Logger(run_logger.Logger):
    @abc.abstractmethod
    def create_sweep(
        self,
        choices: List[ParamChoice],
        metadata: dict,
        method: SweepMethod,
    ) -> int:
        pass


@dataclass
class HasuraLogger(run_logger.HasuraLogger):
    insert_new_sweep_mutation = gql(
        """
mutation insert_new_sweep(
    $grid_index: Int,
    $metadata: jsonb,
    $parameter_choices: [parameter_choices_insert_input!]!,
) {
  insert_sweep_one(object: {
      grid_index: $grid_index,
      metadata: $metadata,
      parameter_choices: {data: $parameter_choices},
      }) {
    grid_index
    id
    metadata
    parameter_choices {
      Key
      choice
    }
  }
}
    """
    )
    add_run_to_sweep_mutation = gql(
        """
mutation add_run_to_sweep($metadata: jsonb = {}, $sweep_id: Int!, $charts: [chart_insert_input!] = []) {
    insert_run_one(object: {charts: {data: $charts}, metadata: $metadata, sweep_id: $sweep_id}) {
        id
        sweep {
            parameter_choices {
                Key
                choice
            }
        }
    }
    update_sweep(where: {id: {_eq: $sweep_id}}, _inc: {grid_index: 1}) {
        returning {
            grid_index
        }
    }
}
    """
    )

    def create_sweep(
        self,
        choices: List[ParamChoice],
        metadata: dict,
        method: SweepMethod,
    ) -> int:
        if method == SweepMethod.grid:
            grid_index = 0
        elif method == SweepMethod.random:
            grid_index = None
        else:
            raise RuntimeError("Invalid value for `method`:", method)

        def preprocess_params(params):
            params = (
                ",".join([json.dumps(json.dumps(v)) for v in params])
                if isinstance(params, list)
                else json.dumps(json.dumps(params))
            )
            return "{" + params + "}"

        response = self.execute(
            self.insert_new_sweep_mutation,
            variable_values=dict(
                grid_index=grid_index,
                metadata=metadata,
                parameter_choices=[
                    dict(Key=k, choice=preprocess_params(vs)) for k, vs in choices
                ],
            ),
        )
        sweep_id = response["insert_sweep_one"]["id"]
        return sweep_id
