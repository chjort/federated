# Lint as: python3
# Copyright 2019, The TensorFlow Federated Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Trains and evaluates a CIFAR-100 classification model using TFF."""

import functools

from absl import app
from absl import flags
from absl import logging
import tensorflow as tf
import tensorflow_federated as tff

from tensorflow_federated.python.research.optimization.cifar100 import dataset
from tensorflow_federated.python.research.optimization.shared import iterative_process_builder
from tensorflow_federated.python.research.optimization.shared import resnet_models
from tensorflow_federated.python.research.utils import training_loop
from tensorflow_federated.python.research.utils import training_utils
from tensorflow_federated.python.research.utils import utils_impl

with utils_impl.record_hparam_flags():
  # Experiment hyperparameters
  flags.DEFINE_integer('client_epochs_per_round', 1,
                       'Number of epochs in the client to take per round.')
  flags.DEFINE_integer('client_batch_size', 32, 'Batch size on the clients.')
  flags.DEFINE_integer('clients_per_round', 2,
                       'How many clients to sample per round.')

  # End of hyperparameter flags.

FLAGS = flags.FLAGS

CIFAR_SHAPE = (32, 32, 3)
CROP_SHAPE = (24, 24, 3)
NUM_CLASSES = 100


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Expected no command-line arguments, '
                         'got: {}'.format(argv))

  tf.compat.v1.enable_v2_behavior()
  # TODO(b/139129100): Remove this once the local executor is the default.
  tff.framework.set_default_executor(
      tff.framework.local_executor_factory(max_fanout=25))

  cifar_train, cifar_test = dataset.get_federated_cifar100(
      client_epochs_per_round=FLAGS.client_epochs_per_round,
      train_batch_size=FLAGS.client_batch_size,
      crop_shape=CROP_SHAPE)

  sample_client_dataset = cifar_train.create_tf_dataset_for_client(
      cifar_train.client_ids[0])

  sample_batch = tf.nest.map_structure(lambda x: x.numpy(),
                                       next(iter(sample_client_dataset)))

  model_builder = functools.partial(
      resnet_models.create_resnet18,
      input_shape=CROP_SHAPE,
      num_classes=NUM_CLASSES)

  logging.info('Training model:')
  logging.info(model_builder().summary())

  loss_builder = tf.keras.losses.SparseCategoricalCrossentropy
  metrics_builder = lambda: [tf.keras.metrics.SparseCategoricalAccuracy()]

  training_process = iterative_process_builder.from_flags(
      dummy_batch=sample_batch,
      model_builder=model_builder,
      loss_builder=loss_builder,
      metrics_builder=metrics_builder)

  training_loop.run(
      iterative_process=training_process,
      client_datasets_fn=training_utils.build_client_datasets_fn(
          cifar_train, FLAGS.clients_per_round),
      evaluate_fn=training_utils.build_evaluate_fn(
          eval_dataset=cifar_test,
          model_builder=model_builder,
          loss_builder=loss_builder,
          metrics_builder=metrics_builder),
  )


if __name__ == '__main__':
  app.run(main)
