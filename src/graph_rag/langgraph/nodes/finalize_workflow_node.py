"""
Finalizes the workflow when the evaluation determines that the workflow is complete or cannot continue:
 - Answers the question if the workflow successfully resolved the plan items
 - Answers the question partially if a partial answer could be produced
 - Stops if an unrecoverable error occurred
"""