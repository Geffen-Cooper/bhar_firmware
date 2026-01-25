# What This Branch Does
- Reads from BMA400 in LP one sample at a time and then does LSTM inference

# Software Config
- Uses updated CMSIS NN library to generate test cases
- Logging disabled in prj.conf

# Hardware Config
- Uses pinout of old PCB in .overlay 

# Random Notes

Generated Code for NN
C:\nordic\bhar\CMSIS-NN\Tests\UnitTest\RefactoredTestGen\TestCases\TestData\

Add use case to
C:\nordic\bhar\CMSIS-NN\Tests\UnitTest\RefactoredTestGen\test_plan.json

To generate the test case
./RefactoredTestGen/generate_test_data.py (specify args for specific tests we want)

See the following for how to call the functions with generated weights and data
C:\nordic\bhar\CMSIS-NN\Tests\UnitTest\TestCases