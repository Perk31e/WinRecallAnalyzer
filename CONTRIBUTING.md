### Contributing Guide

1. First, clone the repository:

   ```
   git clone https://github.com/Perk31e/WinRecallAnalyzer
   ```

2. Next, create a new branch for the feature or changes you want to add. For example, if you're adding the `Recovery_Table` feature:

   ```
   git branch Recovery_Table main
   git checkout Recovery_Table
   ```

3. The branch is now created and checked out. Before starting and periodically during your work, pull the latest changes from the remote `main` branch to keep your branch up to date:

   ```
   git pull origin main
   ```

4. Now, proceed with making code changes and adding features.

5. Once your changes are ready, stage and commit them:

   ```
   git add .
   git commit -m "Brief commit message"
   ```

6. Push your commits to the remote branch:

   ```
   git push origin Recovery_Table
   ```

7. Finally, create a Pull Request on GitHub to submit your changes.
