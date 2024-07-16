import streamlit as st
import gurobipy as gp
from gurobipy import GRB
import pandas as pd

def solve_truck_allocation(Djj):
    model = gp.Model("Truck_Allocation")

    # Sets
    I = ['40', '150', '190', '250', '300']  # Truck types
    J = list(range(1, len(Djj) + 1))  # Nodes based on input length

    # Parameters
    Dj = {j: Djj[j-1] for j in J}
    Qi = {'40': 42, '150': 165, '190': 220, '250': 275, '300': 330}  # Capacity of truck type i
    mi = {'40': 1, '150': 7, '190': 26, '250': 4, '300': 1}  # Number of truck type i available 
    C = 100000  # A very large number

    # Decision variables
    x = model.addVars(I, J, vtype=GRB.BINARY, name="x")
    L = model.addVars(I, J, vtype=GRB.INTEGER, name="L")
    M = model.addVars(I, J, vtype=GRB.INTEGER, name="M")
    y = model.addVars(I, J, vtype=GRB.BINARY, name="y")
    OL = model.addVars(I, J, vtype=GRB.INTEGER, name="OL")
    O = model.addVars(I, J, vtype=GRB.INTEGER, name="O")
    Z = model.addVars(J, vtype=GRB.BINARY, name="Z")

    # Objective function
    model.setObjective(gp.quicksum(M[i, j] * Qi[i] - L[i, j] for i in I for j in J) + C * gp.quicksum(O[i, j] for i in I for j in J), GRB.MINIMIZE)

    # Constraints
    model.addConstrs((M[i, j] <= mi[i] * x[i, j] for i in I for j in J))
    model.addConstrs((gp.quicksum(M[i, j] for j in J) <= mi[i] for i in I))
    model.addConstrs((L[i, j] <= Qi[i] * M[i, j] for i in I for j in J))
    model.addConstrs((gp.quicksum(L[i, j] + OL[i, j] for i in I) == Dj[j] for j in J))
    model.addConstrs((OL[i, j] <= Qi[i] * O[i, j] for i in I for j in J))
    model.addConstrs((O[i, j] <= y[i, j] for i in I for j in J))
    model.addConstrs((Dj[j] <= 40 + C * (1 - Z[j]) for j in J))
    model.addConstrs((x['40', j] <= Z[j] for j in J))

    model.optimize()

    if model.status == GRB.OPTIMAL:
        M_df = pd.DataFrame(index=I, columns=J)
        L_df = pd.DataFrame(index=I, columns=J)
        unused_capacity_df = pd.DataFrame(index=I, columns=J)
        O_df = pd.DataFrame(index=I, columns=J)
        OL_df = pd.DataFrame(index=I, columns=J)
        unused_capacity_outsourced_df = pd.DataFrame(index=I, columns=J)

        for i in I:
            for j in J:
                M_df.loc[i, j] = M[i, j].X
                L_df.loc[i, j] = L[i, j].X
                unused_capacity_df.loc[i, j] = M[i, j].X * Qi[i] - L[i, j].X
                O_df.loc[i, j] = O[i, j].X
                OL_df.loc[i, j] = OL[i, j].X
                unused_capacity_outsourced_df.loc[i, j] = O[i, j].X * Qi[i] - OL[i, j].X

        summary_df = pd.DataFrame(index=J, columns=[
            'Total Trucks Assigned (In-house)', 
            'Total Load Carried (In-house)', 
            'Total Unused Capacity (In-house)', 
            'Total Trucks Assigned (Outsourced)', 
            'Total Load Carried (Outsourced)', 
            'Total Unused Capacity (Outsourced)'
        ])

        for j in J:
            total_trucks_inhouse = sum(M_df.loc[i, j] for i in I)
            total_load_inhouse = sum(L_df.loc[i, j] for i in I)
            total_unused_capacity_inhouse = sum(unused_capacity_df.loc[i, j] for i in I)
            total_trucks_outsourced = sum(O_df.loc[i, j] for i in I)
            total_load_outsourced = sum(OL_df.loc[i, j] for i in I)
            total_unused_capacity_outsourced = sum(unused_capacity_outsourced_df.loc[i, j] for i in I)

            summary_df.loc[j, 'Total Trucks Assigned (In-house)'] = total_trucks_inhouse
            summary_df.loc[j, 'Total Load Carried (In-house)'] = total_load_inhouse
            summary_df.loc[j, 'Total Unused Capacity (In-house)'] = total_unused_capacity_inhouse
            summary_df.loc[j, 'Total Trucks Assigned (Outsourced)'] = total_trucks_outsourced
            summary_df.loc[j, 'Total Load Carried (Outsourced)'] = total_load_outsourced
            summary_df.loc[j, 'Total Unused Capacity (Outsourced)'] = total_unused_capacity_outsourced

        detailed_results = []

        for j in J:
            for i in I:
                if M_df.loc[i, j] > 0:
                    detailed_results.append({
                        'Node': j,
                        'Truck Type': i,
                        'Trucks Assigned (In-house)': M_df.loc[i, j],
                        'Load Carried (In-house)': L_df.loc[i, j],
                        'Unused Capacity (In-house)': unused_capacity_df.loc[i, j],
                        'Trucks Assigned (Outsourced)': O_df.loc[i, j],
                        'Load Carried (Outsourced)': OL_df.loc[i, j],
                        'Unused Capacity (Outsourced)': unused_capacity_outsourced_df.loc[i, j]
                    })

        detailed_df = pd.DataFrame(detailed_results)

        return summary_df, detailed_df
    else:
        return None, None

def main():
    st.title("Truck Allocation Optimization")

    # Get the number of nodes from the user
    num_nodes = st.number_input("Enter the number of nodes:", min_value=1, value=40)

    # Get the demand for each node
    demands = []
    for i in range(num_nodes):
        demand = st.number_input(f"Enter demand for node {i+1}:", min_value=0, value=0)
        demands.append(demand)

    # Button to run the optimization
    if st.button("Optimize"):
        with st.spinner("Running optimization..."):
            summary_df, detailed_df = solve_truck_allocation(demands)

        if summary_df is not None and detailed_df is not None:
            st.success("Optimization completed!")
            
            # Display the summary dataframe
            st.subheader("Summary of Results")
            st.dataframe(summary_df)
            
            # Display the detailed results dataframe
            st.subheader("Detailed Results")
            st.dataframe(detailed_df)
        else:
            st.error("Optimization failed. Please check your inputs.")

if __name__ == "__main__":
    main()
