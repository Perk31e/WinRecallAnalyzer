### 기여 가이드

1. 먼저 리포지토리를 클론합니다.

   ```
   git clone https://github.com/Perk31e/WinRecallAnalyzer
   ```

2. 추가할 기능 또는 변경 사항에 맞는 브랜치를 만듭니다. 예를 들어 `Recovery_Table` 기능을 추가하려면:
   ```
   git branch Recovery_Table main
   git checkout Recovery_Table
   ```
3. 브랜치가 생성되고 전환되었습니다. 작업을 시작하기 전과 작업 도중에도 원격 `main` 브랜치에서 최신 업데이트를 가져와 새 브랜치에 병합합니다.

   ```
   git pull origin main
   ```

4. 이제 코드를 수정하고 기능을 추가합니다.

5. 코드 변경이 완료되면, 변경 사항을 스테이징하고 커밋합니다:

   ```
   git add .
   git commit -m "간단한 커밋 메시지"
   ```

6. 커밋한 내용을 원격 브랜치에 푸시합니다.

   ```
   git push origin Recovery_Table
   ```

7. 마지막으로, GitHub에서 Pull Request를 생성하여 변경 사항을 제출합니다.
