# Copyright 2021-present StarRocks, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FE Config domain: Extract, generate, and persist FE configuration documentation
"""

from docsagent.domains.fe_config.extractor import FEConfigExtractor
from docsagent.domains.fe_config.generator import FEConfigDocGenerator
from docsagent.domains.fe_config.persister import FEConfigPersister
from docsagent.domains.fe_config.git_persister import FEConfigGitPersister

__all__ = [
    'FEConfigExtractor',
    'FEConfigDocGenerator',
    'FEConfigPersister',
    'FEConfigGitPersister',
]
